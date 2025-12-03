from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import models
from .forms import ReservaForm
from .models import Reserva, Servicio, Barbero, HorarioTrabajo 
from datetime import timedelta, datetime, time, date
from django.utils import timezone
import json
import logging 
# Importaciones de autenticacion
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from .forms import CustomUserCreationForm
from .decorators import barbero_required, ajax_login_required

logger = logging.getLogger(__name__)



# ----------------------------------------------------------------------
# FUNCIONES DE NAVEGACION 
# ----------------------------------------------------------------------

def cargarBase(request):
    return render(request, 'base.html')

def cargarCatalogo(request):
    servicios = Servicio.objects.all()
    return render(request, 'catalogo.html', {'servicios': servicios})

def cargarInicio(request):
    servicios = Servicio.objects.all()[:3]
    context = {'servicios': servicios}
    
    # Informacion personalizada segun el tipo de usuario
    if request.user.is_authenticated:
        hoy = date.today()
        
        # Verificar si es barbero
        try:
            barbero = Barbero.objects.get(usuario=request.user)
            # Es barbero - mostrar todas las reservas del dia (simplificado)
            reservas_hoy = Reserva.objects.filter(
                barbero=barbero,
                inicio__date=hoy
            ).select_related('cliente', 'servicio').order_by('inicio')
            
            context.update({
                'es_barbero': True,
                'reservas_hoy': reservas_hoy,
                'barbero': barbero
            })
            
        except Barbero.DoesNotExist:
            # Es cliente - mostrar proximas reservas
            ahora = timezone.now()
            proximas_reservas = Reserva.objects.filter(
                cliente=request.user,
                inicio__gte=ahora,
                estado__in=['Pendiente', 'Confirmada']
            ).select_related('barbero', 'servicio').order_by('inicio')[:3]
            
            context.update({
                'es_cliente': True,
                'proximas_reservas': proximas_reservas
            })
    
    return render(request, 'inicio.html', context)

def confirmacionReserva(request):
    return render(request, 'confirmacionReserva.html')

# ----------------------------------------------------------------------
# REGISTRO DE USUARIO
# ----------------------------------------------------------------------
def registro_usuario(request):
    if request.method == 'POST':
        # Instancia del formulario personalizado con los datos recibidos
        form = CustomUserCreationForm(request.POST) 
        
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Cuenta creada con exito! Ya puedes iniciar sesion.')
            # Redirige a la pagina de login 
            return redirect('login') 
        else:
            # Si el formulario no es valido mostramos los errores en el template
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        # Peticion GET: Muestra el formulario de registro vacio
        form = CustomUserCreationForm()
        
    return render(request, 'registration/registro.html', {'form': form})

def logout_usuario(request):
    """
    Vista personalizada para logout que redirije directamente
    """
    logout(request)
    messages.success(request, '¡Has cerrado sesión exitosamente!')
    return redirect('inicio')


@login_required
def perfil_cliente(request):
    """Vista para el perfil del cliente"""
    # Obtener estadisticas del usuario
    total_reservas = Reserva.objects.filter(cliente=request.user).count()
    reservas_completadas = Reserva.objects.filter(
        cliente=request.user, 
        estado='Completada'
    ).count()
    reservas_pendientes = Reserva.objects.filter(
        cliente=request.user,
        estado__in=['Pendiente', 'Confirmada'],
        inicio__gte=timezone.now()
    ).count()
    
    # Proxima reserva
    proxima_reserva = Reserva.objects.filter(
        cliente=request.user,
        estado__in=['Pendiente', 'Confirmada'],
        inicio__gte=timezone.now()
    ).select_related('barbero', 'servicio').order_by('inicio').first()
    
    # Ultimas reservas (solo 3 para mantener formato)
    ultimas_reservas = Reserva.objects.filter(
        cliente=request.user
    ).select_related('barbero', 'servicio').order_by('-inicio')[:3]
    
    context = {
        'total_reservas': total_reservas,
        'reservas_completadas': reservas_completadas,
        'reservas_pendientes': reservas_pendientes,
        'proxima_reserva': proxima_reserva,
        'ultimas_reservas': ultimas_reservas,
    }
    
    if request.method == 'POST':
        # Actualizar informacion del perfil (solo nombre y apellido)
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.save()
        
        messages.success(request, '¡Perfil actualizado exitosamente!')
        return redirect('perfil_cliente')
    
    return render(request, 'perfil_cliente.html', context)

@login_required
def mis_reservas_cliente(request):
    """Vista para que los clientes vean sus reservas"""
    
    reservas = Reserva.objects.filter(
        cliente=request.user
    ).select_related('barbero', 'servicio').order_by('-inicio')
    
    # Estadisticas rapidas
    total_reservas = reservas.count()
    reservas_confirmadas = reservas.filter(estado='Confirmada').count()
    reservas_pendientes = reservas.filter(estado='Pendiente').count()
    reservas_completadas = reservas.filter(estado='Completada').count()
    
    context = {
        'reservas': reservas,
        'total_reservas': total_reservas,
        'reservas_confirmadas': reservas_confirmadas,
        'reservas_pendientes': reservas_pendientes,
        'reservas_completadas': reservas_completadas,
        'now': timezone.now(),
    }
    
    return render(request, 'mis_reservas_cliente.html', context)

@barbero_required
def agenda_barbero(request):
    """Vista para que los barberos vean su agenda"""
    # El decorador ya verifica autenticacion y permisos
    barbero = Barbero.objects.get(usuario=request.user)
    
    # Obtener reservas del barbero - solo confirmadas y pagadas
    reservas = Reserva.objects.filter(
        barbero=barbero,
        estado__in=['Confirmada', 'Completada'],  # Solo reservas confirmadas o completadas
        pagado=True  # Solo reservas pagadas
    ).select_related('cliente', 'servicio').order_by('-inicio')
    
    # Estadisticas
    hoy = date.today()
    
    reservas_hoy = reservas.filter(inicio__date=hoy).count()
    reservas_pendientes = reservas.filter(estado='Pendiente').count()
    reservas_confirmadas = reservas.filter(estado='Confirmada').count()
    
    # Ingresos del mes (solo reservas completadas y pagadas)
    primer_dia_mes = hoy.replace(day=1)
    ingresos_mes = reservas.filter(
        inicio__date__gte=primer_dia_mes,
        estado='Completada',
        pagado=True
    ).aggregate(
        total=models.Sum('servicio__precio')
    )['total'] or 0
    
    context = {
        'reservas': reservas,
        'barbero': barbero,
        'today': hoy.isoformat(),
        'reservas_hoy': reservas_hoy,
        'reservas_pendientes': reservas_pendientes,
        'reservas_confirmadas': reservas_confirmadas,
        'ingresos_mes': ingresos_mes,
    }
    
    return render(request, 'agenda_barbero.html', context)



def obtener_info_servicio(request):
    """Vista AJAX para obtener informacion del servicio (precio y duracion)"""
    if request.method == 'GET':
        servicio_id = request.GET.get('servicio_id')
        
        if not servicio_id:
            return JsonResponse({'error': 'ID de servicio requerido'})
        
        try:
            servicio = Servicio.objects.get(id=servicio_id)
            return JsonResponse({
                'precio': servicio.precio,
                'duracion': servicio.duracion_minutos,
                'nombre': servicio.nombre,
                'descripcion': servicio.descripcion
            })
        except Servicio.DoesNotExist:
            return JsonResponse({'error': 'Servicio no encontrado'})
    
    return JsonResponse({'error': 'Metodo no permitido'})





def obtener_horas_disponibles_unified(request):
    """Vista unificada para obtener horas disponibles"""
    if request.method == 'GET':
        fecha_str = request.GET.get('fecha')
        barbero_id = request.GET.get('barbero')
        formato = request.GET.get('formato', 'simple')  
        
        if not fecha_str or not barbero_id:
            return JsonResponse({'horas': []})
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            barbero = Barbero.objects.get(id=barbero_id)
        except (ValueError, Barbero.DoesNotExist):
            return JsonResponse({'horas': []})
        
        from .services.availability_service import AvailabilityService
        
        horas_disponibles = AvailabilityService.cleanup_and_get_availability(
            barbero=barbero,
            fecha=fecha,
            formato=formato
        )
        
        if formato == 'completo':
            return JsonResponse({
                'fecha': fecha_str,
                'barbero': barbero.nombre,
                'horas': horas_disponibles
            })
        else:
            # Formato simple para templates Django
            return JsonResponse({'horas': horas_disponibles})
    
    return JsonResponse({'horas': []})

@require_POST
@login_required
def cancelar_reserva(request):
    """Vista para cancelar una reserva (tanto barbero como cliente)"""
    try:
        data = json.loads(request.body)
        reserva_id = data.get('reserva_id')
        
        if not reserva_id:
            return JsonResponse({
                'success': False, 
                'message': 'ID de reserva requerido'
            })
        
        # Obtener la reserva
        try:
            reserva = Reserva.objects.get(id=reserva_id)
        except Reserva.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Reserva no encontrada'
            })
        
        # Verificar permisos: solo el cliente o el barbero pueden cancelar
        es_cliente = reserva.cliente == request.user
        es_barbero = False
        
        try:
            barbero = Barbero.objects.get(usuario=request.user)
            es_barbero = reserva.barbero == barbero
        except Barbero.DoesNotExist:
            pass
        
        if not (es_cliente or es_barbero):
            return JsonResponse({
                'success': False,
                'message': 'No tienes permisos para cancelar esta reserva'
            })
        
        # Verificar que la reserva se pueda cancelar
        if reserva.estado == 'Cancelada':
            return JsonResponse({
                'success': False,
                'message': 'Esta reserva ya estÃ¡ cancelada'
            })
        
        if reserva.estado == 'Completada':
            return JsonResponse({
                'success': False,
                'message': 'No se puede cancelar una reserva completada'
            })
        
        # Verificar tiempo limite 
        tiempo_limite = timezone.now() + timedelta(hours=2)
        
        if reserva.inicio <= tiempo_limite:
            # Calcular tiempo restante para mensaje mas informativo
            tiempo_restante = reserva.inicio - timezone.now()
            horas_restantes = tiempo_restante.total_seconds() / 3600
            
            if horas_restantes < 0:
                mensaje = 'No se puede cancelar una reserva que ya pasó'
            else:
                mensaje = f'No se puede cancelar con menos de 2 horas de anticipación. Faltan {horas_restantes:.1f} horas para la cita'
            
            return JsonResponse({
                'success': False,
                'message': mensaje
            })
        
        # Cancelar la reserva
        reserva.estado = 'Cancelada'
        reserva.save()
        
        # Determinar quien cancelo para el mensaje
        cancelado_por = 'barbero' if es_barbero else 'cliente'
        
        return JsonResponse({
            'success': True,
            'message': 'Reserva cancelada exitosamente',
            'cancelado_por': cancelado_por
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos invÃ¡lidos'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error interno: {str(e)}'
        })


@login_required
def crearReserva(request):
    # Solo los clientes pueden hacer reservas
    if request.user.is_superuser:
        messages.warning(request, 'Los administradores no pueden hacer reservas. Esta función es solo para clientes.')
        return redirect('dashboard')
    
    try:
        barbero = Barbero.objects.get(usuario=request.user)
        messages.warning(request, 'Los barberos no pueden hacer reservas. Esta función es solo para clientes.')
        return redirect('agenda_barbero')
    except Barbero.DoesNotExist:
        pass  # El usuario es un cliente, puede continuar
    
    # Obtener servicio preseleccionado si viene de la pagina de inicio
    servicio_id = request.GET.get('servicio_id')
    initial_data = {}
    if servicio_id:
        try:
            servicio = Servicio.objects.get(id=servicio_id)
            initial_data['servicio'] = servicio
        except Servicio.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = ReservaForm(request.POST)
        if form.is_valid():
            from .services.temporary_reservation_service import TemporaryReservationService
            from .services.mercadopago_service import MercadoPagoService, MercadoPagoServiceError
            
            try:
                logger.info(f"Form is valid. Cleaned data keys: {list(form.cleaned_data.keys())}")
                logger.info(f"Has inicio_calculado: {'inicio_calculado' in form.cleaned_data}")
                logger.info(f"Has fin_calculado: {'fin_calculado' in form.cleaned_data}")
                logger.info(f"User: {request.user.email}, Session: {request.session.session_key}")
                if not request.session.session_key:
                    request.session.create()
                session_key = request.session.session_key
                cliente_email = request.user.email or f"{request.user.username}@noemail.local"
                availability_check = TemporaryReservationService.validate_availability_before_payment(
                    barbero=form.cleaned_data['barbero'],
                    inicio=form.cleaned_data['inicio_calculado'],
                    fin=form.cleaned_data['fin_calculado']
                )
                
                if not availability_check['available']:
                    messages.error(request, availability_check['message'])
                    logger.warning(f"Availability check failed for user {request.user.id}: {availability_check['message']}")
                    return render(request, 'crearReserva.html', {'form': form})
                
                cliente_nombre = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username or "Usuario"
                logger.info(f"Creating temp reservation for: {cliente_email}, name: {cliente_nombre}")
                
                temp_reservation = TemporaryReservationService.create_temporary_reservation(
                    form_data=form.cleaned_data,
                    session_key=session_key,
                    cliente_email=cliente_email,
                    cliente_nombre=cliente_nombre
                )
                
                mp_service = MercadoPagoService()
                preference_data = mp_service.create_preference(temp_reservation)
                
                request.session['temp_reservation_id'] = str(temp_reservation.id)
                request.session['mp_preference_id'] = preference_data['preference_id']
                
                return redirect(preference_data['init_point'])
                
            except MercadoPagoServiceError as e:
                error_message = getattr(e, 'user_message', str(e))
                
                from django.conf import settings
                if settings.DEBUG and getattr(e, 'error_code') == 'invalid_credentials':
                    messages.warning(request, 'âš ï¸ Modo Desarrollo: MercadoPago no estÃ¡ configurado.')
                    messages.info(request, 'Para configurar MercadoPago, agrega tus credenciales en el archivo .env')
                    messages.info(request, 'Por ahora, la reserva se crearÃ¡ sin pago para pruebas.')
                    
                    try:
                        reserva = Reserva.objects.create(
                            cliente=request.user,
                            barbero=form.cleaned_data['barbero'],
                            servicio=form.cleaned_data['servicio'],
                            inicio=form.cleaned_data['inicio_calculado'],
                            fin=form.cleaned_data['fin_calculado'],
                            estado='Confirmada',
                            notas='Reserva creada en modo desarrollo sin pago'
                        )
                        messages.success(request, f'âœ… Reserva creada exitosamente (modo desarrollo)')
                        return redirect('confirmacion_reserva')
                    except Exception as dev_error:
                        messages.error(request, f'Error al crear reserva de desarrollo: {str(dev_error)}')
                else:
                    messages.error(request, error_message)
                    logger.error(f"MercadoPago error for user {request.user.id}: {str(e)} (code: {getattr(e, 'error_code', 'unknown')})")
                    
                    if getattr(e, 'error_code') == 'expired_reservation':
                        messages.info(request, 'Puedes intentar crear una nueva reserva.')
                    elif getattr(e, 'error_code') == 'invalid_credentials':
                        messages.error(request, 'Hay un problema con la configuraciÃ³n del sistema. Por favor contacta al soporte.')
                
            except ValueError as e:
                messages.error(request, str(e))
                logger.warning(f"Validation error in crearReserva for user {request.user.id}: {str(e)}")
            except Exception as e:
                messages.error(request, 'Error inesperado al crear la reserva. Por favor intÃ©ntalo de nuevo.')
                logger.error(f"Unexpected error in crearReserva for user {request.user.id}: {str(e)}", exc_info=True)
        else:
            # Los errores del formulario se mostraran automaticamente en el template
            logger.warning(f"Form is not valid. Errors: {form.errors}")
            logger.warning(f"Form data: {request.POST}")
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = ReservaForm(initial=initial_data)
    
    return render(request, 'crearReserva.html', {'form': form})

def obtener_disponibilidad_detallada(request):
    """Vista para obtener informacion detallada de disponibilidad incluyendo bloqueos temporales"""
    if request.method == 'GET':
        fecha_str = request.GET.get('fecha')
        barbero_id = request.GET.get('barbero')
        
        if not fecha_str or not barbero_id:
            return JsonResponse({'error': 'Fecha y barbero requeridos'})
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            barbero = Barbero.objects.get(id=barbero_id)
        except (ValueError, Barbero.DoesNotExist):
            return JsonResponse({'error': 'Fecha o barbero invalidos'})
        
        from .services.availability_service import AvailabilityService
        
        horas_disponibles = AvailabilityService.get_available_hours_for_date(
            barbero=barbero,
            fecha=fecha,
            formato='completo'
        )
        
        # Obtener horarios bloqueados
        blocked_slots = AvailabilityService.get_blocked_slots_for_date(barbero, fecha)
        
        return JsonResponse({
            'fecha': fecha_str,
            'barbero': {
                'id': barbero.id,
                'nombre': barbero.nombre
            },
            'horas_disponibles': horas_disponibles,
            'reservas_confirmadas': blocked_slots['reservas'],
            'reservas_temporales': blocked_slots['temporary'],
            'total_disponibles': len(horas_disponibles),
            'total_bloqueadas': len(blocked_slots['reservas']) + len(blocked_slots['temporary'])
        })
    
    return JsonResponse({'error': 'Metodo no permitido'})

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json

@csrf_exempt
def cleanup_expired_reservations(request):
    """Limpia reservas temporales expiradas"""
    if request.method == 'POST':
        from .services.cleanup_service import CleanupService
        
        try:
            # Parsear datos del request
            data = {}
            if request.body:
                try:
                    data = json.loads(request.body)
                except json.JSONDecodeError:
                    pass
            
            force_full_cleanup = data.get('full_cleanup', False)
            
            if force_full_cleanup:
                result = CleanupService.full_cleanup()
            else:
                result = CleanupService.cleanup_expired_temporary_reservations()
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)
    
    elif request.method == 'GET':
        from .services.cleanup_service import CleanupService
        
        try:
            stats = CleanupService.get_cleanup_stats()
            return JsonResponse(stats)
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)
    
    return JsonResponse({'error': 'Metodo no permitido'}, status=405)


# ----------------------------------------------------------------------
# VISTAS DE RETORNO DE LA API
# ----------------------------------------------------------------------

def payment_success(request):
    """Vista de retorno cuando el pago es exitoso"""
    try:
        if request.method not in ['GET', 'POST']:
            logger.warning(f"Invalid method {request.method} for payment success callback")
            messages.error(request, 'Metodo de acceso invalido.')
            return redirect('inicio')
        
        # Obtener parametros de la URL
        collection_id = request.GET.get('collection_id')
        collection_status = request.GET.get('collection_status')
        payment_id = request.GET.get('payment_id')
        status = request.GET.get('status')
        external_reference = request.GET.get('external_reference')
        payment_type = request.GET.get('payment_type')
        merchant_order_id = request.GET.get('merchant_order_id')
        preference_id = request.GET.get('preference_id')
        site_id = request.GET.get('site_id')
        processing_mode = request.GET.get('processing_mode')
        merchant_account_id = request.GET.get('merchant_account_id')
        
        # Validar parametros requeridos
        if not (payment_id or collection_id):
            logger.error("Payment success callback missing payment_id and collection_id")
            messages.error(request, 'Faltan parametros requeridos del pago.')
            return redirect('inicio')
        
        # Validar que el status indique exito
        actual_status = status or collection_status
        if actual_status and actual_status not in ['approved', 'authorized']:
            logger.warning(f"Payment success callback with non-success status: {actual_status}")
            messages.warning(request, f'El estado del pago no indica exito: {actual_status}')
            return redirect('payment_failure') + f'?status={actual_status}'
        
        # Obtener el ID de la sesion desde la URL
        temp_reservation_id = request.GET.get('temp_reservation_id')
        if not temp_reservation_id:
            temp_reservation_id = request.session.get('temp_reservation_id')
        
        context = {
            'success': True,
            'payment_id': payment_id or collection_id,
            'status': status or collection_status,
            'external_reference': external_reference,
            'payment_type': payment_type,
            'merchant_order_id': merchant_order_id,
            'preference_id': preference_id,
            'temp_reservation_id': temp_reservation_id,
        }
        
        if temp_reservation_id:
            try:
                from .models import TemporaryReservation, PaymentTransaction
                from django.contrib.auth.models import User
                
                temp_res = TemporaryReservation.objects.get(id=temp_reservation_id)
                
                existing_transaction = PaymentTransaction.objects.filter(
                    temp_reservation=temp_res
                ).first()
                
                if existing_transaction and existing_transaction.reserva:
                    # La reservacion ya existe
                    context.update({
                        'reserva': existing_transaction.reserva,
                        'final_reservation_created': True,
                        'barbero': existing_transaction.reserva.barbero,
                        'servicio': existing_transaction.reserva.servicio,
                        'inicio': existing_transaction.reserva.inicio,
                        'fin': existing_transaction.reserva.fin,
                        'success_message': 'Reserva confirmada exitosamente!'
                    })
                else:
                    try:
                        # Obtener el usuario cliente
                        if request.user.is_authenticated:
                            cliente_user = request.user
                        else:
                            if '@' in temp_res.cliente_email and not temp_res.cliente_email.endswith('@noemail.local'):
                                cliente_user = User.objects.get(email=temp_res.cliente_email)
                            else:
                                username = temp_res.cliente_email.split('@')[0]
                                cliente_user = User.objects.get(username=username)
                        
                        # Crear el pago de la transaccion
                        if not existing_transaction:
                            payment_transaction = PaymentTransaction.objects.create(
                                temp_reservation=temp_res,
                                mp_payment_id=payment_id or f"DEV-{temp_res.id}-{int(datetime.now().timestamp())}",
                                mp_preference_id=preference_id or f"PREF-{temp_res.id}",
                                amount=temp_res.servicio.precio,
                                status='approved',
                                payment_method='credit_card',
                                description=f'Pago procesado para reserva {temp_res.id}',
                                external_reference=external_reference or str(temp_res.id)
                            )
                        else:
                            payment_transaction = existing_transaction
                            payment_transaction.status = 'approved'
                            payment_transaction.save()
                        
                        # Crear reserva final
                        reserva_final = Reserva.objects.create(
                            cliente=cliente_user,
                            barbero=temp_res.barbero,
                            servicio=temp_res.servicio,
                            inicio=temp_res.inicio,
                            fin=temp_res.fin,
                            estado='Confirmada',
                            pagado=True,
                            payment_method='MercadoPago'
                        )
                        
                        # Vincular reserva final con la transaccion
                        payment_transaction.reserva = reserva_final
                        payment_transaction.save()
                        
                        context.update({
                            'reserva': reserva_final,
                            'final_reservation_created': True,
                            'barbero': reserva_final.barbero,
                            'servicio': reserva_final.servicio,
                            'inicio': reserva_final.inicio,
                            'fin': reserva_final.fin,
                            'success_message': 'Pago procesado y reserva confirmada exitosamente!'
                        })
                        
                        logger.info(f"Final reservation created: ID {reserva_final.id} for user {cliente_user.email}")
                        
                    except User.DoesNotExist:
                        logger.error(f"User not found for identifier: {temp_res.cliente_email}")
                        context.update({
                            'temp_reservation': temp_res,
                            'final_reservation_created': False,
                            'barbero': temp_res.barbero,
                            'servicio': temp_res.servicio,
                            'inicio': temp_res.inicio,
                            'fin': temp_res.fin,
                            'error_message': 'Usuario no encontrado. Inicia sesion nuevamente.'
                        })
                    except Exception as e:
                        logger.error(f"Error creating final reservation: {str(e)}")
                        context.update({
                            'temp_reservation': temp_res,
                            'final_reservation_created': False,
                            'barbero': temp_res.barbero,
                            'servicio': temp_res.servicio,
                            'inicio': temp_res.inicio,
                            'fin': temp_res.fin,
                            'error_message': 'Error procesando la reserva. Contacta al soporte.'
                        })
                    
            except TemporaryReservation.DoesNotExist:
                logger.warning(f"Temporary reservation {temp_reservation_id} not found in success callback")
                context['warning_message'] = 'No se encontraron detalles de la reserva, pero el pago fue procesado correctamente.'
        
        # Limpiar datos de la sesion
        if 'temp_reservation_id' in request.session:
            del request.session['temp_reservation_id']
        if 'mp_preference_id' in request.session:
            del request.session['mp_preference_id']
        
        logger.info(f"Payment success callback: payment_id={payment_id}, status={status}, temp_reservation={temp_reservation_id}")
        
        return render(request, 'payment_success.html', context)
        
    except Exception as e:
        logger.error(f"Error in payment success callback: {str(e)}")
        messages.error(request, 'Hubo un error al procesar la confirmacion del pago.')
        return redirect('inicio')


def payment_failure(request):
    """Vista de retorno cuando el pago falla"""
    try:
        # Validar metodo de request
        if request.method not in ['GET', 'POST']:
            logger.warning(f"Invalid method {request.method} for payment failure callback")
            messages.error(request, 'Metodo de acceso invalido.')
            return redirect('inicio')
        
        # Obtener parametros de la URL
        collection_id = request.GET.get('collection_id')
        collection_status = request.GET.get('collection_status')
        payment_id = request.GET.get('payment_id')
        status = request.GET.get('status')
        external_reference = request.GET.get('external_reference')
        payment_type = request.GET.get('payment_type')
        merchant_order_id = request.GET.get('merchant_order_id')
        preference_id = request.GET.get('preference_id')
        
        logger.info(f"Payment failure callback: payment_id={payment_id}, status={status}")
        
        if not (payment_id or collection_id or preference_id):
            logger.error("Payment failure callback missing all payment identifiers")
            messages.error(request, 'No se pudo identificar el pago fallido.')
            return redirect('inicio')
        
        temp_reservation_id = request.GET.get('temp_reservation_id')
        if not temp_reservation_id:
            temp_reservation_id = request.session.get('temp_reservation_id')
        
        context = {
            'success': False,
            'payment_id': payment_id or collection_id,
            'status': status or collection_status,
            'external_reference': external_reference,
            'payment_type': payment_type,
            'merchant_order_id': merchant_order_id,
            'preference_id': preference_id,
            'temp_reservation_id': temp_reservation_id,
        }
        
        if temp_reservation_id:
            try:
                from .models import TemporaryReservation
                temp_res = TemporaryReservation.objects.get(id=temp_reservation_id)
                
                if not temp_res.is_expired:
                    context.update({
                        'temp_reservation': temp_res,
                        'can_retry': True,
                        'barbero': temp_res.barbero,
                        'servicio': temp_res.servicio,
                        'inicio': temp_res.inicio,
                        'fin': temp_res.fin,
                        'expires_at': temp_res.expires_at,
                        'retry_message': f'Tienes hasta las {temp_res.expires_at.strftime("%H:%M")} para completar el pago.'
                    })
                else:
                    context.update({
                        'can_retry': False,
                        'expired_message': 'El tiempo para completar esta reserva ha expirado. Puedes crear una nueva reserva.'
                    })
                    
            except (TemporaryReservation.DoesNotExist, ValueError):
                logger.warning(f"Temporary reservation {temp_reservation_id} not found in failure callback")
                context.update({
                    'can_retry': False,
                    'error_message': 'No se encontraron detalles de la reserva.'
                })
        
        logger.info(f"Payment failure callback: payment_id={payment_id}, status={status}, temp_reservation={temp_reservation_id}")
        
        return render(request, 'payment_failure.html', context)
        
    except Exception as e:
        logger.error(f"Error in payment failure callback: {str(e)}")
        messages.error(request, 'Hubo un error al procesar la respuesta del pago.')
        return redirect('inicio')


def payment_pending(request):
    """Vista de retorno cuando el pago esta pendiente"""
    try:
        # Validar metodo de request
        if request.method not in ['GET', 'POST']:
            logger.warning(f"Invalid method {request.method} for payment pending callback")
            messages.error(request, 'Metodo de acceso invalido.')
            return redirect('inicio')

        # Obtener y validar parametros del callback de MercadoPago
        collection_id = request.GET.get('collection_id')
        collection_status = request.GET.get('collection_status')
        payment_id = request.GET.get('payment_id')
        status = request.GET.get('status')
        external_reference = request.GET.get('external_reference')
        payment_type = request.GET.get('payment_type')
        merchant_order_id = request.GET.get('merchant_order_id')
        preference_id = request.GET.get('preference_id')
        
        logger.info(f"Payment pending callback: payment_id={payment_id}, status={status}")
        
        if not (payment_id or collection_id or preference_id):
            logger.error("Payment pending callback missing all payment identifiers")
            messages.error(request, 'No se pudo identificar el pago pendiente.')
            return redirect('inicio')
 
        temp_reservation_id = request.GET.get('temp_reservation_id')
        if not temp_reservation_id:
            temp_reservation_id = request.session.get('temp_reservation_id')
        
        context = {
            'pending': True,
            'payment_id': payment_id or collection_id,
            'status': status or collection_status,
            'external_reference': external_reference,
            'payment_type': payment_type,
            'merchant_order_id': merchant_order_id,
            'preference_id': preference_id,
            'temp_reservation_id': temp_reservation_id,
        }
        
        if temp_reservation_id:
            try:
                from .models import TemporaryReservation
                temp_res = TemporaryReservation.objects.get(id=temp_reservation_id)
                
                context.update({
                    'temp_reservation': temp_res,
                    'barbero': temp_res.barbero,
                    'servicio': temp_res.servicio,
                    'inicio': temp_res.inicio,
                    'fin': temp_res.fin,
                    'expires_at': temp_res.expires_at,
                })
                
                if payment_type in ['bank_transfer', 'atm']:
                    context['pending_message'] = 'Tu pago esta siendo procesado por el banco. Te notificaremos cuando se confirme.'
                elif payment_type == 'ticket':
                    context['pending_message'] = 'Tu pago en efectivo esta pendiente. Una vez que realices el pago, se confirmara automaticamente.'
                else:
                    context['pending_message'] = 'Tu pago esta siendo procesado. Te notificaremos cuando se confirme.'
                    
            except (TemporaryReservation.DoesNotExist, ValueError):
                logger.warning(f"Temporary reservation {temp_reservation_id} not found in pending callback")
                context['warning_message'] = 'No se encontraron detalles de la reserva, pero el pago esta siendo procesado.'
        
        logger.info(f"Payment pending callback: payment_id={payment_id}, status={status}, temp_reservation={temp_reservation_id}")
        
        return render(request, 'payment_pending.html', context)
        
    except Exception as e:
        logger.error(f"Error in payment pending callback: {str(e)}")
        messages.error(request, 'Hubo un error al procesar la respuesta del pago.')
        return redirect('inicio')


# ----------------------------------------------------------------------
# MERCADOPAGO WEBHOOK ENDPOINT
# ----------------------------------------------------------------------

@csrf_exempt
def mercadopago_webhook(request):
    """
    Handle MercadoPago webhook notifications.
    Validates webhook authenticity and processes payment updates asynchronously.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        # Obtener metadatos del request para logging
        request_meta = {
            'headers': dict(request.headers),
            'ip': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'query_params': dict(request.GET)
        }
        
        # Parsear payload del webhook
        try:
            webhook_data = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Validar firma del webhook si esta configurado
        from .services.mercadopago_service import MercadoPagoService, MercadoPagoServiceError
        
        try:
            mp_service = MercadoPagoService()
            
            # Obtener headers de firma
            signature = request.headers.get('x-signature', '')
            user_id = request.headers.get('x-user-id', '')
            
            # Validar firma si el secreto del webhook esta configurado
            if hasattr(mp_service, 'webhook_secret') and mp_service.webhook_secret:
                if not mp_service.validate_webhook_signature(request.body, signature, user_id):
                    logger.error(f"Invalid webhook signature from IP {request_meta['ip']}")
                    return JsonResponse({'error': 'Invalid signature'}, status=401)
            else:
                logger.warning("Webhook signature validation skipped - no secret configured")
            
            # Procesar webhook de forma asincrona
            success, message = mp_service.process_webhook(webhook_data, request_meta)
            
            if success:
                logger.info(f"Webhook processed successfully: {message}")
                return JsonResponse({'status': 'ok', 'message': message})
            else:
                logger.error(f"Webhook processing failed: {message}")
                return JsonResponse({'error': message}, status=500)
                
        except MercadoPagoServiceError as e:
            logger.error(f"MercadoPago service error in webhook: {str(e)} (code: {getattr(e, 'error_code', 'unknown')})")
            return JsonResponse({
                'error': 'Service error',
                'error_code': getattr(e, 'error_code', 'unknown')
            }, status=500)
        
    except Exception as e:
        logger.error(f"Unexpected error in webhook endpoint: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def retry_payment(request):
    """
    Allow users to retry payment for an existing temporary reservation.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        data = json.loads(request.body)
        temp_reservation_id = data.get('temp_reservation_id')
        
        if not temp_reservation_id:
            return JsonResponse({'error': 'temp_reservation_id required'}, status=400)
        
        from .models import TemporaryReservation
        from .services.mercadopago_service import MercadoPagoService, MercadoPagoServiceError
        
        # Obtener reserva temporal
        try:
            temp_reservation = TemporaryReservation.objects.get(
                id=temp_reservation_id,
                cliente_email=request.user.email
            )
        except TemporaryReservation.DoesNotExist:
            return JsonResponse({'error': 'Temporary reservation not found'}, status=404)
        
        # Verificar si la reserva aun es valida
        if temp_reservation.is_expired:
            return JsonResponse({'error': 'Temporary reservation has expired'}, status=400)
        
        # Verificar si el horario aun esta disponible
        from .services.temporary_reservation_service import TemporaryReservationService
        
        if not TemporaryReservationService.is_time_slot_available(
            temp_reservation.barbero, 
            temp_reservation.inicio, 
            temp_reservation.fin,
            exclude_temp_reservation=temp_reservation
        ):
            return JsonResponse({'error': 'Time slot is no longer available'}, status=400)
        
        # Crear nueva preferencia de MercadoPago
        try:
            mp_service = MercadoPagoService()
            preference_data = mp_service.create_preference(temp_reservation)
            
            # Actualizar datos de sesion
            request.session['temp_reservation_id'] = str(temp_reservation.id)
            request.session['mp_preference_id'] = preference_data['preference_id']
            
            return JsonResponse({
                'success': True,
                'init_point': preference_data['init_point'],
                'preference_id': preference_data['preference_id']
            })
            
        except MercadoPagoServiceError as e:
            error_message = getattr(e, 'user_message', 'Error del servicio de pagos')
            logger.error(f"Error creating retry preference: {str(e)} (code: {getattr(e, 'error_code', 'unknown')})")
            return JsonResponse({
                'error': error_message,
                'error_code': getattr(e, 'error_code', 'unknown')
            }, status=500)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in retry payment: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
def reserva_payment_details(request, reserva_id):
    """
    API endpoint to get payment details for a specific reservation.
    Only accessible by the barbero or the client who made the reservation.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET method allowed'}, status=405)
    
    try:
        # Obtener la reserva
        try:
            reserva = Reserva.objects.select_related(
                'cliente', 'servicio', 'barbero'
            ).get(id=reserva_id)
        except Reserva.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Reserva no encontrada'
            }, status=404)
        
        # Verificar permisos: solo barbero o cliente pueden acceder
        es_cliente = reserva.cliente == request.user
        es_barbero = False
        
        try:
            barbero = Barbero.objects.get(usuario=request.user)
            es_barbero = reserva.barbero == barbero
        except Barbero.DoesNotExist:
            pass
        
        if not (es_cliente or es_barbero):
            return JsonResponse({
                'success': False,
                'message': 'No tienes permisos para ver esta informaciÃ³n'
            }, status=403)
        
        # Obtener detalles de la transaccion de pago
        payment_details = None
        try:
            from .models import PaymentTransaction
            transaction = PaymentTransaction.objects.get(reserva=reserva)
            
            payment_details = {
                'mp_payment_id': transaction.mp_payment_id,
                'mp_preference_id': transaction.mp_preference_id,
                'amount': str(transaction.amount),
                'status': transaction.status,
                'payment_method': transaction.payment_method or 'MercadoPago',
                'created_at': transaction.created_at.strftime('%d/%m/%Y %H:%M'),
                'updated_at': transaction.updated_at.strftime('%d/%m/%Y %H:%M'),
            }
        except PaymentTransaction.DoesNotExist:
            # No payment transaction found - might be an old reservation
            payment_details = {
                'mp_payment_id': None,
                'mp_preference_id': None,
                'amount': str(reserva.servicio.precio),
                'status': 'approved' if reserva.pagado else 'pending',
                'payment_method': reserva.payment_method or 'MercadoPago',
                'created_at': reserva.fecha_creacion.strftime('%d/%m/%Y %H:%M') if hasattr(reserva, 'fecha_creacion') else 'N/A',
                'updated_at': 'N/A',
            }
        
        # Prepare reservation details
        reserva_details = {
            'id': reserva.id,
            'cliente_nombre': f"{reserva.cliente.first_name} {reserva.cliente.last_name}".strip() or reserva.cliente.username,
            'cliente_email': reserva.cliente.email,
            'servicio_nombre': reserva.servicio.nombre,
            'barbero_nombre': reserva.barbero.nombre,
            'fecha_formateada': reserva.inicio.strftime('%A, %d de %B de %Y'),
            'hora_inicio': reserva.inicio.strftime('%H:%M'),
            'hora_fin': reserva.fin.strftime('%H:%M'),
            'estado': reserva.estado,
            'pagado': reserva.pagado,
        }
        
        return JsonResponse({
            'success': True,
            'payment_details': payment_details,
            'reserva': reserva_details
        })
        
    except Exception as e:
        logger.error(f"Error getting payment details for reservation {reserva_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error interno del servidor'
        }, status=500)


# ======================================================================
# GESTIÃ“N DE BARBEROS (Solo para staff)
# ======================================================================

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from .forms import BarberoForm

@staff_member_required
def gestionar_barberos(request):
    """Lista todos los barberos"""
    barberos = Barbero.objects.all().select_related('usuario')
    return render(request, 'barberos/lista.html', {'barberos': barberos})

@staff_member_required
def crear_barbero(request):
    """Crea un nuevo barbero"""
    if request.method == 'POST':
        form = BarberoForm(request.POST, request.FILES)
        if form.is_valid():
            barbero = form.save()
            
            # Mensaje de Ã©xito
            messages.success(
                request, 
                f'âœ… Barbero "{barbero.nombre}" creado exitosamente con usuario "{barbero.usuario.username}".'
            )
            messages.info(
                request,
                f'ðŸ“§ Credenciales: Usuario: {barbero.usuario.username} | Email: {barbero.usuario.email}'
            )
            
            return redirect('gestionar_barberos')
    else:
        form = BarberoForm()
    
    return render(request, 'barberos/form.html', {
        'form': form,
        'titulo': 'Crear Nuevo Barbero',
        'accion': 'Crear'
    })

@staff_member_required
def editar_barbero(request, barbero_id):
    """Edita un barbero existente"""
    barbero = get_object_or_404(Barbero, pk=barbero_id)
    
    if request.method == 'POST':
        form = BarberoForm(request.POST, request.FILES, instance=barbero)
        if form.is_valid():
            barbero = form.save()
            messages.success(request, f'âœ… Barbero "{barbero.nombre}" actualizado exitosamente.')
            return redirect('gestionar_barberos')
    else:
        form = BarberoForm(instance=barbero)
    
    return render(request, 'barberos/form.html', {
        'form': form,
        'barbero': barbero,
        'titulo': f'Editar: {barbero.nombre}',
        'accion': 'Actualizar'
    })

@staff_member_required
def eliminar_barbero(request, barbero_id):
    """Elimina un barbero"""
    barbero = get_object_or_404(Barbero, pk=barbero_id)
    
    if request.method == 'POST':
        nombre = barbero.nombre
        barbero.delete()
        messages.success(request, f'Barbero "{nombre}" eliminado exitosamente.')
        return redirect('gestionar_barberos')
    
    reservas_count = Reserva.objects.filter(barbero=barbero).count()
    
    return render(request, 'barberos/eliminar.html', {
        'barbero': barbero,
        'reservas_count': reservas_count
    })






# ======================================================================
# CONTACTO
# ======================================================================

def contacto(request):
    """Página de contacto con información de la barbería"""
    context = {
        'telefono': '+569 34135145',
        'email': 'info@cronocorte.cl',
        'direccion': 'Nueva Oriente 9537, El Bosque',
        'whatsapp': '56934135145',  # Sin + ni espacios para el link
        'instagram': 'https://www.instagram.com/jamonbarber/',
        'instagram_user': '@jamonbarber',
        'horarios': {
            'lunes_viernes': '18:00 - 21:00',
            'sabado': '09:00 - 18:00',
            'domingo': 'Cerrado'
        }
    }
    return render(request, 'contacto.html', context)


# ----------------------------------------------------------------------
# VISTAS DE ERROR PERSONALIZADAS
# ----------------------------------------------------------------------

def custom_404(request, exception=None):
    """Vista personalizada para error 404 - Página no encontrada"""
    return render(request, '404.html', status=404)


def custom_500(request):
    """Vista personalizada para error 500 - Error del servidor"""
    return render(request, '500.html', status=500)


def custom_403(request, exception=None):
    """Vista personalizada para error 403 - Acceso denegado"""
    return render(request, '403.html', status=403)
