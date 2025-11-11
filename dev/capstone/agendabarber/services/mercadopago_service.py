"""
MercadoPago Service Layer
Handles all interactions with MercadoPago API including payment preferences,
payment verification, and webhook processing.
"""

import mercadopago
import logging
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from agendabarber.models import Reserva
from django.conf import settings
from django.utils import timezone as django_timezone
from agendabarber.models import PaymentTransaction, TemporaryReservation, PaymentWebhookLog

logger = logging.getLogger(__name__)


class MercadoPagoServiceError(Exception):
    """Custom exception for MercadoPago service errors"""
    def __init__(self, message, error_code=None, user_message=None):
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or self._get_user_friendly_message(message, error_code)
    
    def _get_user_friendly_message(self, message, error_code):
        """Convert technical error messages to user-friendly ones"""
        error_mappings = {
            'connection_error': 'No se pudo conectar con el servicio de pagos. Inténtalo de nuevo.',
            'invalid_credentials': 'Error de configuración del sistema de pagos. Contacta al soporte.',
            'preference_creation_failed': 'No se pudo crear la preferencia de pago. Inténtalo de nuevo.',
            'payment_verification_failed': 'No se pudo verificar el estado del pago. Inténtalo de nuevo.',
            'webhook_processing_failed': 'Error procesando la notificación de pago.',
            'expired_reservation': 'El tiempo para completar esta reserva ha expirado.',
            'invalid_payment_data': 'Los datos del pago son inválidos.',
            'api_error': 'Error en el servicio de pagos. Inténtalo de nuevo en unos minutos.',
        }
        
        # Try to match error code first
        if error_code and error_code in error_mappings:
            return error_mappings[error_code]
        
        # Try to match message patterns
        message_lower = message.lower()
        if 'connection' in message_lower or 'timeout' in message_lower:
            return error_mappings['connection_error']
        elif 'credential' in message_lower or 'authentication' in message_lower:
            return error_mappings['invalid_credentials']
        elif 'expired' in message_lower:
            return error_mappings['expired_reservation']
        elif 'preference' in message_lower:
            return error_mappings['preference_creation_failed']
        else:
            return 'Ocurrió un error con el sistema de pagos. Por favor inténtalo de nuevo.'


class MercadoPagoService:
    """
    Service class for handling MercadoPago API operations.
    
    This service provides methods to:
    - Initialize SDK with proper credentials
    - Create payment preferences
    - Verify payment status
    - Process webhook notifications
    """
    
    def __init__(self):
        """Initialize MercadoPago SDK with credentials from settings"""
        try:
            self.access_token = settings.MERCADOPAGO_ACCESS_TOKEN
            logger.info(f"Initializing MercadoPago with token: {self.access_token[:20]}..." if self.access_token else "No token found")
            
            if not self.access_token:
                logger.error("MercadoPago access token not configured")
                raise MercadoPagoServiceError(
                    "MERCADOPAGO_ACCESS_TOKEN not configured",
                    error_code='invalid_credentials',
                    user_message='Error de configuración del sistema de pagos. Contacta al soporte.'
                )
            
            # Initialize MercadoPago SDK
            try:
                self.sdk = mercadopago.SDK(self.access_token)
            except Exception as sdk_error:
                logger.error(f"Failed to initialize MercadoPago SDK: {str(sdk_error)}")
                raise MercadoPagoServiceError(
                    f"SDK initialization failed: {str(sdk_error)}",
                    error_code='invalid_credentials'
                )
            
            # Store configuration
            self.sandbox_mode = getattr(settings, 'MERCADOPAGO_SANDBOX', True)
            self.webhook_secret = getattr(settings, 'MERCADOPAGO_WEBHOOK_SECRET', None)
            
            # URLs for redirects
            self.success_url = getattr(settings, 'MERCADOPAGO_SUCCESS_URL', '')
            self.failure_url = getattr(settings, 'MERCADOPAGO_FAILURE_URL', '')
            self.pending_url = getattr(settings, 'MERCADOPAGO_PENDING_URL', '')
            self.webhook_url = getattr(settings, 'MERCADOPAGO_WEBHOOK_URL', '')
            
            # Validate required URLs
            if not all([self.success_url, self.failure_url, self.pending_url]):
                logger.warning("Some MercadoPago callback URLs are not configured")
            
            logger.info(f"MercadoPago SDK initialized in {'sandbox' if self.sandbox_mode else 'production'} mode")
            
        except MercadoPagoServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing MercadoPago SDK: {str(e)}")
            raise MercadoPagoServiceError(
                f"SDK initialization failed: {str(e)}",
                error_code='api_error'
            )
    
    def create_preference(self, temp_reservation: TemporaryReservation, additional_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a payment preference for a temporary reservation.
        
        Args:
            temp_reservation: TemporaryReservation instance with payment details
            additional_config: Optional additional configuration for the preference
            
        Returns:
            Dict containing preference data including init_point for redirect
            
        Raises:
            MercadoPagoServiceError: If preference creation fails
        """
        try:
            # Validate temporary reservation
            if temp_reservation.is_expired:
                logger.error(f"Attempted to create preference for expired temp reservation {temp_reservation.id}")
                raise MercadoPagoServiceError(
                    "Cannot create preference for expired temporary reservation",
                    error_code='expired_reservation'
                )
            
            # Validate amount
            try:
                amount = float(temp_reservation.servicio.precio)
                if amount <= 0:
                    raise ValueError("Invalid amount")
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid service price for temp reservation {temp_reservation.id}: {temp_reservation.servicio.precio}")
                raise MercadoPagoServiceError(
                    f"Invalid service price: {temp_reservation.servicio.precio}",
                    error_code='invalid_payment_data'
                )
            
            # Create external reference for tracking
            external_reference = f"temp_reservation_{temp_reservation.id}"
            
            # Build preference data with service details
            try:
                preference_data = self._build_preference_data(
                    temp_reservation=temp_reservation,
                    amount=amount,
                    external_reference=external_reference,
                    additional_config=additional_config or {}
                )
            except Exception as e:
                logger.error(f"Error building preference data: {str(e)}")
                raise MercadoPagoServiceError(
                    f"Error building payment data: {str(e)}",
                    error_code='invalid_payment_data'
                )
            
            # Create preference via MercadoPago API with retry logic
            max_retries = 3
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    preference_response = self.sdk.preference().create(preference_data)
                    break
                except Exception as api_error:
                    last_error = api_error
                    logger.warning(f"MercadoPago API attempt {attempt + 1} failed: {str(api_error)}")
                    if attempt == max_retries - 1:
                        logger.error(f"All {max_retries} attempts to create preference failed")
                        raise MercadoPagoServiceError(
                            f"Failed to create payment preference after {max_retries} attempts: {str(last_error)}",
                            error_code='api_error'
                        )
            
            # Validate API response
            if preference_response["status"] != 201:
                error_details = preference_response.get('response', {})
                error_msg = f"MercadoPago API returned status {preference_response['status']}: {error_details}"
                logger.error(error_msg)
                
                # Extract specific error information if available
                if isinstance(error_details, dict) and 'message' in error_details:
                    user_error = f"Error del servicio de pagos: {error_details['message']}"
                else:
                    user_error = "No se pudo crear la preferencia de pago. Inténtalo de nuevo."
                
                raise MercadoPagoServiceError(
                    error_msg,
                    error_code='preference_creation_failed',
                    user_message=user_error
                )
            
            preference = preference_response["response"]
            
            # Validate preference response structure
            if not preference.get("id") or not preference.get("init_point"):
                logger.error(f"Invalid preference response structure: {preference}")
                raise MercadoPagoServiceError(
                    "Invalid response from payment service",
                    error_code='api_error'
                )
            
            # Update temporary reservation with preference ID
            try:
                temp_reservation.mp_preference_id = preference["id"]
                temp_reservation.save(update_fields=['mp_preference_id'])
            except Exception as e:
                logger.error(f"Failed to update temp reservation with preference ID: {str(e)}")
                # Don't fail the whole process for this
            
            logger.info(f"Created MercadoPago preference {preference['id']} for temp reservation {temp_reservation.id}")
            
            # Return preference information
            result = {
                "preference_id": preference["id"],
                "init_point": preference["sandbox_init_point"] if self.sandbox_mode else preference["init_point"],
                "external_reference": external_reference,
                "amount": amount,
                "currency": "CLP",
                "expires_at": temp_reservation.expires_at.isoformat()
            }
            
            # Include both URLs for flexibility
            if self.sandbox_mode:
                result["sandbox_init_point"] = preference["sandbox_init_point"]
                result["production_init_point"] = preference["init_point"]
            else:
                result["production_init_point"] = preference["init_point"]
                if "sandbox_init_point" in preference:
                    result["sandbox_init_point"] = preference["sandbox_init_point"]
            
            return result
            
        except MercadoPagoServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating MercadoPago preference: {str(e)}")
            raise MercadoPagoServiceError(
                f"Preference creation failed: {str(e)}",
                error_code='api_error'
            )
    
    def _build_preference_data(self, temp_reservation: TemporaryReservation, amount: float, 
                              external_reference: str, additional_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build preference data structure with service details and configuration.
        CONFIGURACIÓN MÍNIMA PARA SANDBOX CHILE
        """
        # Build callback URLs
        success_url = self._build_callback_url(self.success_url, temp_reservation.id)
        failure_url = self._build_callback_url(self.failure_url, temp_reservation.id)
        pending_url = self._build_callback_url(self.pending_url, temp_reservation.id)
        
        # Log URLs for debugging
        logger.info(f"Building preference with URLs - Success: {success_url}, Failure: {failure_url}, Pending: {pending_url}")
        
        # Configuración mínima que funciona en sandbox Chile
        preference_data = {
            "items": [
                {
                    "title": f"Reserva - {temp_reservation.servicio.nombre}",
                    "quantity": 1,
                    "currency_id": "CLP",
                    "unit_price": amount
                }
            ],
            "payer": {
                "email": temp_reservation.cliente_email
            },
            "external_reference": external_reference
        }
        
        # Only add back_urls and auto_return if URLs are properly configured
        if success_url and failure_url and pending_url:
            preference_data["back_urls"] = {
                "success": success_url,
                "failure": failure_url,
                "pending": pending_url
            }
            preference_data["auto_return"] = "approved"
        else:
            logger.warning("Back URLs not fully configured, skipping auto_return")
        
        return preference_data
    
    def _build_item_description(self, temp_reservation: TemporaryReservation) -> str:
        """
        Build detailed item description for the payment.
        
        Args:
            temp_reservation: TemporaryReservation instance
            
        Returns:
            Formatted description string
        """
        inicio_formatted = temp_reservation.inicio.strftime('%d/%m/%Y %H:%M')
        duracion = temp_reservation.servicio.duracion_minutos
        
        description_parts = [
            f"Servicio: {temp_reservation.servicio.nombre}",
            f"Barbero: {temp_reservation.barbero.nombre}",
            f"Fecha y hora: {inicio_formatted}",
            f"Duración: {duracion} minutos"
        ]
        
        if temp_reservation.servicio.descripcion:
            description_parts.append(f"Descripción: {temp_reservation.servicio.descripcion}")
        
        return " | ".join(description_parts)
    
    def _build_callback_url(self, base_url: str, temp_reservation_id: str) -> str:
        """
        Build callback URL with temporary reservation ID for tracking.
        
        Args:
            base_url: Base callback URL
            temp_reservation_id: Temporary reservation UUID
            
        Returns:
            Complete callback URL with parameters
        """
        if not base_url:
            return ""
        
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}temp_reservation_id={temp_reservation_id}"
    
    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Verify payment status by querying MercadoPago API.
        
        Args:
            payment_id: MercadoPago payment ID to verify
            
        Returns:
            Dict containing payment information
            
        Raises:
            MercadoPagoServiceError: If payment verification fails
        """
        try:
            # Validate payment ID format
            if not payment_id or not str(payment_id).isdigit():
                logger.error(f"Invalid payment ID format: {payment_id}")
                raise MercadoPagoServiceError(
                    f"Invalid payment ID format: {payment_id}",
                    error_code='invalid_payment_data'
                )
            
            # Attempt to get payment with retry logic
            max_retries = 3
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    payment_response = self.sdk.payment().get(payment_id)
                    break
                except Exception as api_error:
                    last_error = api_error
                    logger.warning(f"Payment verification attempt {attempt + 1} failed: {str(api_error)}")
                    if attempt == max_retries - 1:
                        logger.error(f"All {max_retries} attempts to verify payment {payment_id} failed")
                        raise MercadoPagoServiceError(
                            f"Failed to verify payment after {max_retries} attempts: {str(last_error)}",
                            error_code='payment_verification_failed'
                        )
            
            # Validate API response
            if payment_response["status"] != 200:
                error_details = payment_response.get('response', {})
                error_msg = f"MercadoPago API returned status {payment_response['status']} for payment {payment_id}: {error_details}"
                logger.error(error_msg)
                
                # Handle specific error cases
                if payment_response["status"] == 404:
                    raise MercadoPagoServiceError(
                        f"Payment {payment_id} not found",
                        error_code='invalid_payment_data',
                        user_message=f"No se encontró el pago {payment_id}"
                    )
                else:
                    raise MercadoPagoServiceError(
                        error_msg,
                        error_code='payment_verification_failed'
                    )
            
            payment_data = payment_response["response"]
            
            # Validate payment data structure
            required_fields = ["id", "status"]
            missing_fields = [field for field in required_fields if field not in payment_data]
            if missing_fields:
                logger.error(f"Payment {payment_id} response missing required fields: {missing_fields}")
                raise MercadoPagoServiceError(
                    f"Invalid payment data structure: missing {missing_fields}",
                    error_code='api_error'
                )
            
            logger.info(f"Retrieved payment {payment_id} with status {payment_data.get('status')}")
            
            return {
                "id": payment_data["id"],
                "status": payment_data["status"],
                "status_detail": payment_data.get("status_detail"),
                "amount": payment_data.get("transaction_amount"),
                "currency": payment_data.get("currency_id"),
                "payment_method": payment_data.get("payment_method_id"),
                "payment_type": payment_data.get("payment_type_id"),
                "external_reference": payment_data.get("external_reference"),
                "description": payment_data.get("description"),
                "date_created": payment_data.get("date_created"),
                "date_approved": payment_data.get("date_approved"),
                "merchant_order_id": payment_data.get("order", {}).get("id") if payment_data.get("order") else None,
                "metadata": payment_data.get("metadata", {})
            }
            
        except MercadoPagoServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error verifying payment {payment_id}: {str(e)}")
            raise MercadoPagoServiceError(
                f"Payment verification failed: {str(e)}",
                error_code='payment_verification_failed'
            )
    
    def validate_webhook_signature(self, request_body: bytes, signature: str, user_id: str = None) -> bool:
        """
        Validate webhook signature to ensure authenticity.
        
        Args:
            request_body: Raw request body as bytes
            signature: Signature from x-signature header
            user_id: Optional user ID from x-user-id header
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping signature validation")
            return True
        
        try:
            # MercadoPago uses different signature formats
            # Try v1 format first: "ts=timestamp,v1=signature"
            if self._validate_v1_signature(request_body, signature):
                return True
            
            # Try alternative format with user_id
            if user_id and self._validate_user_signature(request_body, signature, user_id):
                return True
            
            logger.error("All webhook signature validation methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Error validating webhook signature: {str(e)}")
            return False
    
    def _validate_v1_signature(self, request_body: bytes, signature: str) -> bool:
        """Validate v1 signature format"""
        try:
            signature_parts = {}
            for part in signature.split(','):
                if '=' in part:
                    key, value = part.split('=', 1)
                    signature_parts[key] = value
            
            timestamp = signature_parts.get('ts')
            v1_signature = signature_parts.get('v1')
            
            if not timestamp or not v1_signature:
                return False
            
            # Create expected signature
            payload = f"{timestamp}.{request_body.decode('utf-8')}"
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, v1_signature)
            
        except Exception:
            return False
    
    def _validate_user_signature(self, request_body: bytes, signature: str, user_id: str) -> bool:
        """Validate signature with user ID"""
        try:
            # Alternative validation method using user_id
            payload = f"{user_id}{request_body.decode('utf-8')}"
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception:
            return False
    
    def process_webhook(self, webhook_data: Dict[str, Any], request_meta: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        Process webhook notification from MercadoPago.
        
        Args:
            webhook_data: Parsed webhook payload
            request_meta: Optional request metadata (headers, IP, etc.)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        webhook_log = None
        
        try:
            # Extract webhook information
            topic = webhook_data.get('topic', webhook_data.get('type', 'unknown'))
            resource_id = webhook_data.get('data', {}).get('id') or webhook_data.get('id')
            
            if not resource_id:
                return False, "No resource ID found in webhook data"
            
            # Create webhook log for auditing
            webhook_log = PaymentWebhookLog.objects.create(
                topic=topic if topic in dict(PaymentWebhookLog.WEBHOOK_TOPIC_CHOICES) else 'other',
                resource_id=str(resource_id),
                request_body=webhook_data,
                request_headers=request_meta.get('headers', {}) if request_meta else {},
                request_query_params=request_meta.get('query_params', {}) if request_meta else {},
                source_ip=request_meta.get('ip') if request_meta else None,
                user_agent=request_meta.get('user_agent') if request_meta else None,
                processing_status='processing'
            )
            
            # Only process payment-related webhooks
            if topic not in ['payment', 'merchant_order']:
                webhook_log.processing_status = 'ignored'
                webhook_log.save()
                return True, f"Webhook topic '{topic}' ignored"
            
            # Process payment webhook
            if topic == 'payment':
                success, message = self._process_payment_webhook(resource_id, webhook_log)
            else:
                # For merchant_order, we might need to handle differently
                success, message = self._process_merchant_order_webhook(resource_id, webhook_log)
            
            if success:
                webhook_log.mark_as_processed()
            else:
                webhook_log.mark_as_failed(message)
            
            return success, message
            
        except Exception as e:
            error_msg = f"Error processing webhook: {str(e)}"
            logger.error(error_msg)
            
            if webhook_log:
                webhook_log.mark_as_failed(error_msg)
            
            return False, error_msg
    
    def _process_payment_webhook(self, payment_id: str, webhook_log: PaymentWebhookLog) -> Tuple[bool, str]:
        """
        Process a payment webhook notification.
        Handles different payment states: approved, rejected, pending, etc.
        
        Args:
            payment_id: MercadoPago payment ID
            webhook_log: WebhookLog instance for tracking
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get payment details from MercadoPago
            payment_info = self.verify_payment(payment_id)
            
            # Find existing transaction or create new one
            transaction, created = PaymentTransaction.objects.get_or_create(
                mp_payment_id=payment_id,
                defaults=self._build_transaction_defaults(payment_info)
            )
            
            # Update webhook log relationship
            webhook_log.payment_transaction = transaction
            webhook_log.save()
            
            # Track status changes for logging
            old_status = transaction.status if not created else None
            new_status = payment_info['status']
            
            # Update transaction with latest payment info
            self._update_transaction_from_payment_info(transaction, payment_info)
            
            # Find associated temporary reservation if not already linked
            if not transaction.temp_reservation and payment_info.get('external_reference'):
                self._link_temporary_reservation(transaction, payment_info['external_reference'])
            
            # Handle payment status changes
            status_change_result = self._handle_payment_status_change(
                transaction, old_status, new_status
            )
            
            if not status_change_result[0]:
                return status_change_result
            
            # Log status change if it occurred
            if old_status and old_status != new_status:
                logger.info(f"Payment {payment_id} status changed from {old_status} to {new_status}")
            
            return True, f"Payment {payment_id} processed successfully (status: {new_status})"
            
        except Exception as e:
            error_msg = f"Error processing payment webhook {payment_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _build_transaction_defaults(self, payment_info: Dict[str, Any]) -> Dict[str, Any]:
        """Build default values for creating a new PaymentTransaction"""
        return {
            'mp_preference_id': payment_info.get('external_reference', '').replace('temp_reservation_', '') if payment_info.get('external_reference') else '',
            'amount': Decimal(str(payment_info['amount'])) if payment_info['amount'] else Decimal('0'),
            'currency': payment_info.get('currency', 'CLP'),
            'status': payment_info['status'],
            'status_detail': payment_info.get('status_detail'),
            'payment_method': self._map_payment_method(payment_info.get('payment_method')),
            'payment_type': payment_info.get('payment_type'),
            'external_reference': payment_info.get('external_reference'),
            'description': payment_info.get('description'),
            'mp_merchant_order_id': payment_info.get('merchant_order_id')
        }
    
    def _update_transaction_from_payment_info(self, transaction: PaymentTransaction, payment_info: Dict[str, Any]):
        """Update transaction with latest payment information"""
        # Update basic fields
        transaction.status = payment_info['status']
        transaction.status_detail = payment_info.get('status_detail')
        transaction.payment_method = self._map_payment_method(payment_info.get('payment_method'))
        transaction.payment_type = payment_info.get('payment_type')
        transaction.mp_merchant_order_id = payment_info.get('merchant_order_id')
        
        # Parse and update MercadoPago dates
        if payment_info.get('date_created'):
            try:
                date_created_str = payment_info['date_created']
                # Handle different date formats from MercadoPago
                if date_created_str.endswith('Z'):
                    date_created_str = date_created_str.replace('Z', '+00:00')
                elif not date_created_str.endswith('+00:00') and 'T' in date_created_str:
                    date_created_str += '+00:00'
                
                transaction.mp_date_created = datetime.fromisoformat(date_created_str)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse date_created '{payment_info['date_created']}': {e}")
        
        if payment_info.get('date_approved'):
            try:
                date_approved_str = payment_info['date_approved']
                if date_approved_str.endswith('Z'):
                    date_approved_str = date_approved_str.replace('Z', '+00:00')
                elif not date_approved_str.endswith('+00:00') and 'T' in date_approved_str:
                    date_approved_str += '+00:00'
                
                transaction.mp_date_approved = datetime.fromisoformat(date_approved_str)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse date_approved '{payment_info['date_approved']}': {e}")
        
        transaction.save()
    
    def _link_temporary_reservation(self, transaction: PaymentTransaction, external_reference: str):
        """Link transaction to temporary reservation using external reference"""
        try:
            if external_reference and external_reference.startswith('temp_reservation_'):
                temp_reservation_id = external_reference.replace('temp_reservation_', '')
                temp_reservation = TemporaryReservation.objects.get(id=temp_reservation_id)
                transaction.temp_reservation = temp_reservation
                transaction.mp_preference_id = temp_reservation.mp_preference_id or ''
                transaction.save()
                logger.info(f"Linked transaction {transaction.mp_payment_id} to temp reservation {temp_reservation_id}")
        except TemporaryReservation.DoesNotExist:
            logger.warning(f"Temporary reservation {temp_reservation_id} not found for transaction {transaction.mp_payment_id}")
        except Exception as e:
            logger.error(f"Error linking temporary reservation: {str(e)}")
    
    def _handle_payment_status_change(self, transaction: PaymentTransaction, old_status: str, new_status: str) -> Tuple[bool, str]:
        """
        Handle payment status changes and trigger appropriate actions.
        
        Args:
            transaction: PaymentTransaction instance
            old_status: Previous payment status
            new_status: New payment status
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Handle approved payments
            if new_status in ['approved', 'authorized'] and not transaction.reserva:
                if transaction.temp_reservation:
                    success, message = self._create_final_reservation(transaction)
                    if not success:
                        return False, f"Failed to create reservation: {message}"
                    return True, f"Reservation created for approved payment {transaction.mp_payment_id}"
                else:
                    logger.warning(f"Approved payment {transaction.mp_payment_id} has no temporary reservation")
                    return True, "Payment approved but no temporary reservation found"
            
            # Handle rejected/cancelled payments
            elif new_status in ['rejected', 'cancelled']:
                if transaction.temp_reservation and not transaction.temp_reservation.is_expired:
                    # Clean up temporary reservation for failed payments
                    transaction.temp_reservation.delete()
                    logger.info(f"Cleaned up temporary reservation for failed payment {transaction.mp_payment_id}")
                return True, f"Payment {transaction.mp_payment_id} marked as {new_status}"
            
            # Handle pending payments
            elif new_status in ['pending', 'in_process', 'in_mediation']:
                # Keep temporary reservation active for pending payments
                logger.info(f"Payment {transaction.mp_payment_id} is pending, keeping temporary reservation")
                return True, f"Payment {transaction.mp_payment_id} is pending"
            
            # Handle refunded/charged back payments
            elif new_status in ['refunded', 'charged_back']:
                # If there's a final reservation, we might need to handle cancellation
                if transaction.reserva:
                    # For now, just log it - business logic for handling refunds can be added later
                    logger.warning(f"Payment {transaction.mp_payment_id} was {new_status}, reservation {transaction.reserva.id} may need attention")
                return True, f"Payment {transaction.mp_payment_id} marked as {new_status}"
            
            # Unknown status
            else:
                logger.warning(f"Unknown payment status '{new_status}' for payment {transaction.mp_payment_id}")
                return True, f"Payment {transaction.mp_payment_id} has unknown status {new_status}"
            
        except Exception as e:
            error_msg = f"Error handling status change for payment {transaction.mp_payment_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _process_merchant_order_webhook(self, order_id: str, webhook_log: PaymentWebhookLog) -> Tuple[bool, str]:
        """
        Process a merchant order webhook notification.
        
        Args:
            order_id: MercadoPago merchant order ID
            webhook_log: WebhookLog instance for tracking
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        # For now, we'll just log merchant order webhooks
        # In the future, this could be used for additional order processing
        logger.info(f"Received merchant order webhook for order {order_id}")
        return True, f"Merchant order {order_id} webhook logged"
    
    def _create_final_reservation(self, transaction: PaymentTransaction) -> Tuple[bool, str]:
        """
        Create final reservation from successful payment transaction.
        
        Args:
            transaction: PaymentTransaction with successful payment
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            from agendabarber.models import Reserva
            from django.contrib.auth.models import User
            
            if not transaction.temp_reservation:
                return False, "No temporary reservation found for transaction"
            
            temp_res = transaction.temp_reservation
            
            # Find or create user based on email
            try:
                user = User.objects.get(email=temp_res.cliente_email)
            except User.DoesNotExist:
                # Create a new user account
                username = temp_res.cliente_email.split('@')[0]
                # Ensure username is unique
                counter = 1
                original_username = username
                while User.objects.filter(username=username).exists():
                    username = f"{original_username}{counter}"
                    counter += 1
                
                user = User.objects.create_user(
                    username=username,
                    email=temp_res.cliente_email,
                    first_name=temp_res.cliente_nombre.split()[0] if temp_res.cliente_nombre else '',
                    last_name=' '.join(temp_res.cliente_nombre.split()[1:]) if len(temp_res.cliente_nombre.split()) > 1 else ''
                )
                logger.info(f"Created new user {username} for email {temp_res.cliente_email}")
            
            # Create final reservation
            reserva = Reserva.objects.create(
                cliente=user,
                barbero=temp_res.barbero,
                servicio=temp_res.servicio,
                inicio=temp_res.inicio,
                fin=temp_res.fin,
                pagado=True,
                payment_method='mercadopago',
                estado='Confirmada'
            )
            
            # Link transaction to final reservation
            transaction.reserva = reserva
            transaction.save()
            
            # Clean up temporary reservation using dedicated method
            cleanup_success, cleanup_message = self.cleanup_temporary_reservation_after_success(transaction)
            if not cleanup_success:
                logger.warning(f"Failed to clean up temporary reservation: {cleanup_message}")
            
            logger.info(f"Created final reservation {reserva.id} from payment {transaction.mp_payment_id}")
            
            return True, f"Reservation {reserva.id} created successfully"
            
        except Exception as e:
            error_msg = f"Error creating final reservation: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _map_payment_method(self, mp_payment_method: str) -> str:
        """
        Map MercadoPago payment method to our internal choices.
        
        Args:
            mp_payment_method: MercadoPago payment method ID
            
        Returns:
            Mapped payment method for our model
        """
        if not mp_payment_method:
            return 'other'
        
        method_mapping = {
            # Credit Cards
            'visa': 'credit_card',
            'master': 'credit_card',
            'amex': 'credit_card',
            'diners': 'credit_card',
            'naranja': 'credit_card',
            'cabal': 'credit_card',
            'cencosud': 'credit_card',
            'cmr': 'credit_card',
            'argencard': 'credit_card',
            
            # Debit Cards
            'maestro': 'debit_card',
            'debvisa': 'debit_card',
            'debmaster': 'debit_card',
            'redcompra': 'debit_card',
            'debcabal': 'debit_card',
            
            # Bank Transfers
            'webpay': 'bank_transfer',
            'khipu': 'bank_transfer',
            'pse': 'bank_transfer',
            'bancomer': 'bank_transfer',
            'banamex': 'bank_transfer',
            'serfin': 'bank_transfer',
            
            # Digital Wallets
            'account_money': 'digital_wallet',
            'mercadopago_cc': 'digital_wallet',
            'consumer_credits': 'digital_wallet',
            
            # Cash
            'rapipago': 'cash',
            'pagofacil': 'cash',
            'bapropagos': 'cash',
            'cargavirtual': 'cash',
            'redlink': 'cash',
            'oxxo': 'cash',
            'bancoppel': 'cash',
            'banamex': 'cash'
        }
        
        return method_mapping.get(mp_payment_method.lower(), 'other')
    
    def get_payment_status_display(self, status: str) -> str:
        """
        Get human-readable display text for payment status.
        
        Args:
            status: MercadoPago payment status
            
        Returns:
            Human-readable status text
        """
        status_display = {
            'pending': 'Pago Pendiente',
            'approved': 'Pago Aprobado',
            'authorized': 'Pago Autorizado',
            'in_process': 'Pago en Proceso',
            'in_mediation': 'Pago en Mediación',
            'rejected': 'Pago Rechazado',
            'cancelled': 'Pago Cancelado',
            'refunded': 'Pago Reembolsado',
            'charged_back': 'Contracargo'
        }
        
        return status_display.get(status, f'Estado Desconocido ({status})')
    
    def is_webhook_duplicate(self, payment_id: str, topic: str, received_at: datetime) -> bool:
        """
        Check if webhook is a duplicate based on recent logs.
        
        Args:
            payment_id: Payment ID from webhook
            topic: Webhook topic
            received_at: When webhook was received
            
        Returns:
            True if this appears to be a duplicate webhook
        """
        try:
            # Check for recent webhooks with same payment_id and topic (within last 5 minutes)
            recent_threshold = received_at - timedelta(minutes=5)
            
            recent_webhooks = PaymentWebhookLog.objects.filter(
                topic=topic,
                resource_id=payment_id,
                received_at__gte=recent_threshold,
                processing_status__in=['processed', 'processing']
            ).count()
            
            return recent_webhooks > 0
            
        except Exception as e:
            logger.error(f"Error checking for duplicate webhook: {str(e)}")
            return False
    
    def create_reservation_from_payment(self, payment_id: str) -> Tuple[bool, str, Optional['Reserva']]:
        """
        Create final reservation from successful payment.
        Public method to create reservation when payment is approved.
        
        Args:
            payment_id: MercadoPago payment ID
            
        Returns:
            Tuple of (success: bool, message: str, reserva: Optional[Reserva])
        """
        try:
            # Get the payment transaction
            transaction = PaymentTransaction.objects.get(mp_payment_id=payment_id)
            
            # Verify payment is successful
            if not transaction.is_successful:
                return False, f"Payment {payment_id} is not successful (status: {transaction.status})", None
            
            # Check if reservation already exists
            if transaction.reserva:
                return True, f"Reservation already exists for payment {payment_id}", transaction.reserva
            
            # Create the final reservation
            success, message = self._create_final_reservation(transaction)
            
            if success:
                # Reload transaction to get the created reserva
                transaction.refresh_from_db()
                return True, message, transaction.reserva
            else:
                return False, message, None
                
        except PaymentTransaction.DoesNotExist:
            return False, f"Payment transaction {payment_id} not found", None
        except Exception as e:
            error_msg = f"Error creating reservation from payment {payment_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    def cleanup_temporary_reservation_after_success(self, transaction: PaymentTransaction) -> Tuple[bool, str]:
        """
        Clean up temporary reservation after successful payment and final reservation creation.
        Updates PaymentTransaction with final reserva reference.
        
        Args:
            transaction: PaymentTransaction with successful payment
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            if not transaction.temp_reservation:
                return True, "No temporary reservation to clean up"
            
            if not transaction.reserva:
                return False, "Cannot clean up temporary reservation without final reservation"
            
            temp_reservation_id = transaction.temp_reservation.id
            
            # Delete the temporary reservation
            transaction.temp_reservation.delete()
            
            # Clear the temp_reservation reference (it's now deleted)
            transaction.temp_reservation = None
            transaction.save(update_fields=['temp_reservation'])
            
            logger.info(f"Cleaned up temporary reservation {temp_reservation_id} after successful payment {transaction.mp_payment_id}")
            
            return True, f"Temporary reservation {temp_reservation_id} cleaned up successfully"
            
        except Exception as e:
            error_msg = f"Error cleaning up temporary reservation for transaction {transaction.mp_payment_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def cleanup_expired_temporary_reservations(self) -> int:
        """
        Clean up expired temporary reservations.
        This method can be called periodically to maintain database hygiene.
        
        Returns:
            Number of expired reservations cleaned up
        """
        try:
            expired_count = TemporaryReservation.objects.cleanup_expired()
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired temporary reservations")
            return expired_count
        except Exception as e:
            logger.error(f"Error cleaning up expired temporary reservations: {str(e)}")
            return 0