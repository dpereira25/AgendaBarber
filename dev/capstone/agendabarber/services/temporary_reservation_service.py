"""
Service for managing temporary reservations during the payment process.
Handles creation, validation, and cleanup of temporary reservations.
"""

from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from ..models import TemporaryReservation, Reserva
import logging

logger = logging.getLogger(__name__)


class TemporaryReservationService:
    """Service class for managing temporary reservations"""
    
    EXPIRATION_MINUTES = 15  # Temporary reservations expire after 15 minutes
    
    @classmethod
    def create_temporary_reservation(cls, form_data, session_key, cliente_email, cliente_nombre):
        """
        Create a temporary reservation to block a time slot during payment process.
        
        Args:
            form_data (dict): Validated form data containing barbero, servicio, fecha, hora
            session_key (str): User's session key for tracking
            cliente_email (str): Client's email address
            cliente_nombre (str): Client's name
            
        Returns:
            TemporaryReservation: Created temporary reservation
            
        Raises:
            ValueError: If the time slot is not available
        """
        barbero = form_data['barbero']
        servicio = form_data['servicio']
        inicio = form_data['inicio_calculado']
        fin = form_data['fin_calculado']
        
        # Validate input parameters with detailed logging
        missing_params = []
        if not barbero:
            missing_params.append('barbero')
        if not servicio:
            missing_params.append('servicio')
        if not inicio:
            missing_params.append('inicio_calculado')
        if not fin:
            missing_params.append('fin_calculado')
        if not session_key:
            missing_params.append('session_key')
        if not cliente_email:
            missing_params.append('cliente_email')
        
        if missing_params:
            error_msg = f"Faltan parámetros requeridos para crear la reserva temporal: {', '.join(missing_params)}"
            logger.error(f"Missing parameters in create_temporary_reservation: {missing_params}")
            logger.error(f"Form data received: {form_data}")
            raise ValueError(error_msg)
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, cliente_email):
            raise ValueError("El formato del email no es válido")
        
        # Validate that the time slot is still available
        if not cls.is_time_slot_available(barbero, inicio, fin):
            raise ValueError("El horario seleccionado ya no está disponible")
        
        # Create temporary reservation with atomic transaction and retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    # Clean up expired reservations first
                    cls.cleanup_expired_reservations()
                    
                    # Double-check availability within transaction
                    if not cls.is_time_slot_available(barbero, inicio, fin):
                        raise ValueError("El horario seleccionado ya no está disponible")
                    
                    # Check for existing temp reservation for this session
                    existing_temp = TemporaryReservation.objects.active().filter(
                        session_key=session_key,
                        barbero=barbero,
                        inicio=inicio
                    ).first()
                    
                    if existing_temp:
                        # Update existing reservation instead of creating new one
                        existing_temp.cliente_email = cliente_email
                        existing_temp.cliente_nombre = cliente_nombre
                        existing_temp.expires_at = timezone.now() + timedelta(minutes=cls.EXPIRATION_MINUTES)
                        existing_temp.save()
                        logger.info(f"Updated existing temporary reservation {existing_temp.id} for {cliente_email}")
                        return existing_temp
                    
                    # Calculate expiration time
                    expires_at = timezone.now() + timedelta(minutes=cls.EXPIRATION_MINUTES)
                    
                    # Create temporary reservation
                    temp_reservation = TemporaryReservation.objects.create(
                        session_key=session_key,
                        barbero=barbero,
                        servicio=servicio,
                        inicio=inicio,
                        fin=fin,
                        cliente_email=cliente_email,
                        cliente_nombre=cliente_nombre,
                        expires_at=expires_at
                    )
                    
                    logger.info(f"Created temporary reservation {temp_reservation.id} for {cliente_email}")
                    return temp_reservation
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    logger.error(f"Failed to create temporary reservation after {max_retries} attempts: {str(e)}")
                    if "already exists" in str(e).lower() or "unique constraint" in str(e).lower():
                        raise ValueError("Ya existe una reserva temporal para este horario. Inténtalo de nuevo.")
                    else:
                        raise ValueError("Error al crear la reserva temporal. Inténtalo de nuevo.")
                else:
                    # Retry after short delay
                    import time
                    time.sleep(0.1 * (attempt + 1))  # Progressive delay
                    logger.warning(f"Temporary reservation creation attempt {attempt + 1} failed, retrying: {str(e)}")
        
        # This should never be reached due to the exception handling above
        raise ValueError("Error inesperado al crear la reserva temporal")
    
    @classmethod
    def is_time_slot_available(cls, barbero, inicio, fin, exclude_temp_reservation=None):
        """
        Check if a time slot is available (not blocked by existing reservations or temp reservations).
        
        Args:
            barbero: Barbero instance
            inicio (datetime): Start time of the slot
            fin (datetime): End time of the slot
            exclude_temp_reservation: TemporaryReservation to exclude from check (for retries)
            
        Returns:
            bool: True if available, False if blocked
        """
        from django.db import transaction
        
        # Use atomic transaction to ensure consistency
        with transaction.atomic():
            # Clean up expired reservations first
            cls.cleanup_expired_reservations()
            
            # Check for existing confirmed reservations
            existing_reservas = Reserva.objects.filter(
                barbero=barbero,
                inicio__lt=fin,
                fin__gt=inicio,
                estado__in=['Pendiente', 'Confirmada']
            ).exists()
            
            if existing_reservas:
                return False
            
            # Check for active temporary reservations
            temp_query = TemporaryReservation.objects.active().filter(
                barbero=barbero,
                inicio__lt=fin,
                fin__gt=inicio
            )
            
            # Exclude specific temporary reservation if provided (for retry scenarios)
            if exclude_temp_reservation:
                temp_query = temp_query.exclude(id=exclude_temp_reservation.id)
            
            temp_reservations = temp_query.exists()
            
            return not temp_reservations
    
    @classmethod
    def get_by_session(cls, session_key):
        """
        Get active temporary reservations for a session.
        
        Args:
            session_key (str): User's session key
            
        Returns:
            QuerySet: Active temporary reservations for the session
        """
        return TemporaryReservation.objects.active().filter(session_key=session_key)
    
    @classmethod
    def get_by_id(cls, temp_reservation_id):
        """
        Get a temporary reservation by ID if it's still active.
        
        Args:
            temp_reservation_id: UUID of the temporary reservation
            
        Returns:
            TemporaryReservation or None: The reservation if found and active
        """
        try:
            return TemporaryReservation.objects.active().get(id=temp_reservation_id)
        except TemporaryReservation.DoesNotExist:
            return None
    
    @classmethod
    def cleanup_expired_reservations(cls):
        """
        Clean up all expired temporary reservations.
        
        Returns:
            int: Number of expired reservations cleaned up
        """
        expired_count = TemporaryReservation.objects.cleanup_expired()
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired temporary reservations")
        return expired_count
    
    @classmethod
    def extend_expiration(cls, temp_reservation, additional_minutes=5):
        """
        Extend the expiration time of a temporary reservation.
        
        Args:
            temp_reservation: TemporaryReservation instance
            additional_minutes (int): Minutes to add to expiration
            
        Returns:
            TemporaryReservation: Updated reservation
        """
        if temp_reservation.is_expired:
            raise ValueError("Cannot extend an already expired reservation")
        
        temp_reservation.expires_at += timedelta(minutes=additional_minutes)
        temp_reservation.save(update_fields=['expires_at'])
        
        logger.info(f"Extended temporary reservation {temp_reservation.id} by {additional_minutes} minutes")
        return temp_reservation
    
    @classmethod
    def validate_availability_before_payment(cls, barbero, inicio, fin, exclude_temp_reservation=None):
        """
        Validate that a time slot is still available before proceeding with payment.
        This is used as a final check before creating MercadoPago preferences.
        
        Args:
            barbero: Barbero instance
            inicio (datetime): Start time of the slot
            fin (datetime): End time of the slot
            exclude_temp_reservation: TemporaryReservation to exclude from check
            
        Returns:
            dict: Validation result with success status and message
        """
        try:
            # Clean up expired reservations first
            cls.cleanup_expired_reservations()
            
            # Check availability
            if not cls.is_time_slot_available(barbero, inicio, fin, exclude_temp_reservation):
                # Get specific conflict information
                conflict_info = cls._get_availability_conflict_details(barbero, inicio, fin, exclude_temp_reservation)
                return {
                    'available': False,
                    'message': conflict_info['message'],
                    'conflict_type': conflict_info['type']
                }
            
            return {
                'available': True,
                'message': 'Horario disponible'
            }
            
        except Exception as e:
            logger.error(f"Error validating availability: {str(e)}")
            return {
                'available': False,
                'message': 'Error al verificar disponibilidad. Inténtalo de nuevo.',
                'error': str(e)
            }
    
    @classmethod
    def _get_availability_conflict_details(cls, barbero, inicio, fin, exclude_temp_reservation=None):
        """
        Get detailed information about availability conflicts
        """
        from ..models import Reserva
        
        # Check for confirmed reservations
        existing_reserva = Reserva.objects.filter(
            barbero=barbero,
            inicio__lt=fin,
            fin__gt=inicio,
            estado__in=['Pendiente', 'Confirmada']
        ).first()
        
        if existing_reserva:
            return {
                'type': 'confirmed_reservation',
                'message': f'Ya existe una reserva confirmada de {existing_reserva.inicio.strftime("%H:%M")} a {existing_reserva.fin.strftime("%H:%M")}.'
            }
        
        # Check for temporary reservations
        temp_query = TemporaryReservation.objects.active().filter(
            barbero=barbero,
            inicio__lt=fin,
            fin__gt=inicio
        )
        
        if exclude_temp_reservation:
            temp_query = temp_query.exclude(id=exclude_temp_reservation.id)
        
        temp_reserva = temp_query.first()
        
        if temp_reserva:
            expires_in = temp_reserva.time_remaining
            minutes_remaining = max(1, int(expires_in.total_seconds() / 60))
            return {
                'type': 'temporary_reservation',
                'message': f'Este horario está temporalmente bloqueado (se libera en {minutes_remaining} minutos).'
            }
        
        return {
            'type': 'unknown',
            'message': 'El horario ya no está disponible.'
        }
    
    @classmethod
    def convert_to_final_reservation(cls, temp_reservation, cliente_user):
        """
        Convert a temporary reservation to a final confirmed reservation.
        
        Args:
            temp_reservation: TemporaryReservation instance
            cliente_user: User instance for the client
            
        Returns:
            Reserva: Created final reservation
        """
        if temp_reservation.is_expired:
            raise ValueError("Cannot convert an expired temporary reservation")
        
        with transaction.atomic():
            # Final availability check before conversion
            if not cls.is_time_slot_available(
                temp_reservation.barbero, 
                temp_reservation.inicio, 
                temp_reservation.fin,
                exclude_temp_reservation=temp_reservation
            ):
                raise ValueError("Time slot is no longer available for final reservation")
            
            # Create final reservation
            reserva = Reserva.objects.create(
                cliente=cliente_user,
                barbero=temp_reservation.barbero,
                servicio=temp_reservation.servicio,
                inicio=temp_reservation.inicio,
                fin=temp_reservation.fin,
                pagado=True,
                payment_method='mercadopago',
                estado='Confirmada'
            )
            
            # Delete temporary reservation
            temp_reservation.delete()
            
            logger.info(f"Converted temporary reservation to final reservation {reserva.id}")
            return reserva