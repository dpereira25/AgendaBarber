from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import ReservaForm
from .models import Reserva, Servicio, Barbero 
from datetime import timedelta, datetime, time
from django.utils import timezone
from django.db.models import Q 

# 💡 Nuevas importaciones para autenticación
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

# ----------------------------------------------------------------------
# REGLAS DE HORARIO FIJO (Se mantiene)
# ----------------------------------------------------------------------
HORARIO_SEMANAL = {'inicio': time(18, 0), 'fin': time(21, 0)} 
HORARIO_SABADO = {'inicio': time(9, 0), 'fin': time(18, 0)}

# ----------------------------------------------------------------------
# FUNCIONES DE NAVEGACIÓN (Se mantienen)
# ----------------------------------------------------------------------

def cargarBase(request):
    return render(request, 'base.html')

def cargarCatalogo(request):
    servicios = Servicio.objects.all()
    return render(request, 'catalogo.html', {'servicios': servicios})

def cargarInicio(request):
    servicios = Servicio.objects.all()[:3]
    context = {'servicios': servicios}
    
    # Información personalizada según el tipo de usuario
    if request.user.is_authenticated:
        from datetime import date, datetime, timedelta
        hoy = date.today()
        
        # Verificar si es barbero
        try:
            barbero = Barbero.objects.get(usuario=request.user)
            # Es barbero - mostrar reservas pendientes del día
            reservas_hoy = Reserva.objects.filter(
                barbero=barbero,
                inicio__date=hoy,
                estado='Pendiente'
            ).select_related('cliente', 'servicio').order_by('inicio')
            
            context.update({
                'es_barbero': True,
                'reservas_hoy': reservas_hoy,
                'barbero': barbero
            })
            
        except Barbero.DoesNotExist:
            # Es cliente - mostrar próximas reservas
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
# 💡 NUEVA FUNCIÓN: REGISTRO DE USUARIO
# ----------------------------------------------------------------------
def registro_usuario(request):
    if request.method == 'POST':
        # Instancia del formulario con los datos recibidos (ej. usuario, contraseña 1, contraseña 2)
        form = UserCreationForm(request.POST) 
        
        if form.is_valid():
            user = form.save()
            messages.success(request, '¡Cuenta creada con éxito! Ya puedes iniciar sesión.')
            # Redirige a la página de login (definida en las urls de django.contrib.auth)
            return redirect('login') 
        else:
            # Si el formulario no es válido (ej. contraseñas no coinciden, usuario ya existe),
            # mostramos los errores en el template.
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        # Petición GET: Muestra el formulario de registro vacío
        form = UserCreationForm()
        
    return render(request, 'registration/registro.html', {'form': form})

def logout_usuario(request):
    """
    Vista personalizada para logout que redirije directamente
    """
    logout(request)
    messages.success(request, '¡Has cerrado sesión exitosamente!')
    return redirect('inicio')

from django.http import JsonResponse
from django.db.models import Q, Sum
from django.db import models
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json

def es_barbero(user):
    """Función helper para verificar si un usuario es barbero"""
    if not user.is_authenticated:
        return False
    try:
        Barbero.objects.get(usuario=user)
        return True
    except Barbero.DoesNotExist:
        return False

def mis_reservas_cliente(request):
    """Vista para que los clientes vean sus reservas"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    reservas = Reserva.objects.filter(
        cliente=request.user
    ).select_related('barbero', 'servicio').order_by('-inicio')
    
    # Estadísticas rápidas
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

def agenda_barbero(request):
    """Vista para que los barberos vean su agenda"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Verificar si el usuario es barbero
    try:
        barbero = Barbero.objects.get(usuario=request.user)
    except Barbero.DoesNotExist:
        messages.error(request, 'No tienes permisos de barbero. Contacta al administrador.')
        return redirect('inicio')
    
    # Obtener reservas del barbero
    reservas = Reserva.objects.filter(
        barbero=barbero
    ).select_related('cliente', 'servicio').order_by('-inicio')
    
    # Estadísticas
    from datetime import date
    hoy = date.today()
    
    reservas_hoy = reservas.filter(inicio__date=hoy).count()
    reservas_pendientes = reservas.filter(estado='Pendiente').count()
    reservas_confirmadas = reservas.filter(estado='Confirmada').count()
    
    # Ingresos del mes (solo reservas completadas y pagadas)
    from datetime import datetime
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

def obtener_horas_disponibles(request):
    """Vista AJAX para obtener horas disponibles según fecha y barbero"""
    if request.method == 'GET':
        fecha_str = request.GET.get('fecha')
        barbero_id = request.GET.get('barbero')
        
        if not fecha_str or not barbero_id:
            return JsonResponse({'horas': []})
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            barbero = Barbero.objects.get(id=barbero_id)
        except (ValueError, Barbero.DoesNotExist):
            return JsonResponse({'horas': []})
        
        # Determinar horario según el día
        dia_semana = fecha.isoweekday()
        if 1 <= dia_semana <= 5:  # Lunes a viernes
            hora_inicio = time(18, 0)
            hora_fin = time(21, 0)
        elif dia_semana == 6:  # Sábado
            hora_inicio = time(9, 0)
            hora_fin = time(18, 0)
        else:  # Domingo
            return JsonResponse({'horas': []})
        
        # Generar horas disponibles (cada hora)
        horas_disponibles = []
        hora_actual = hora_inicio
        
        while hora_actual < hora_fin:
            # Verificar si esta hora está ocupada
            inicio_slot = timezone.make_aware(datetime.combine(fecha, hora_actual))
            fin_slot = inicio_slot + timedelta(hours=1)
            
            ocupado = Reserva.objects.filter(
                barbero=barbero,
                inicio__date=fecha,
                estado__in=['Pendiente', 'Confirmada'],
                inicio__lt=fin_slot,
                fin__gt=inicio_slot
            ).exists()
            
            if not ocupado:
                horas_disponibles.append({
                    'value': hora_actual.strftime('%H:%M'),
                    'text': hora_actual.strftime('%H:%M')
                })
            
            # Avanzar una hora
            hora_actual = (datetime.combine(fecha, hora_actual) + timedelta(hours=1)).time()
        
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
                'message': 'Esta reserva ya está cancelada'
            })
        
        if reserva.estado == 'Completada':
            return JsonResponse({
                'success': False,
                'message': 'No se puede cancelar una reserva completada'
            })
        
        # Verificar tiempo límite (opcional: no cancelar si falta menos de 2 horas)
        from datetime import timedelta
        tiempo_limite = timezone.now() + timedelta(hours=2)
        
        if reserva.inicio <= tiempo_limite:
            return JsonResponse({
                'success': False,
                'message': 'No se puede cancelar con menos de 2 horas de anticipación'
            })
        
        # Cancelar la reserva
        reserva.estado = 'Cancelada'
        reserva.save()
        
        # Determinar quién canceló para el mensaje
        cancelado_por = 'barbero' if es_barbero else 'cliente'
        
        return JsonResponse({
            'success': True,
            'message': 'Reserva cancelada exitosamente',
            'cancelado_por': cancelado_por
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Datos inválidos'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error interno: {str(e)}'
        })


# ----------------------------------------------------------------------
# 💡 FUNCIÓN DE CREACIÓN DE RESERVA (Actualizada con @login_required)
# ----------------------------------------------------------------------

@login_required
def crearReserva(request):
    # Obtener servicio preseleccionado si viene de la página de inicio
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
            # El formulario ya validó todo, solo necesitamos crear la reserva
            reserva = form.save(commit=False)
            reserva.cliente = request.user
            
            # Usar los valores calculados por el formulario
            cleaned_data = form.cleaned_data
            reserva.inicio = cleaned_data['inicio_calculado']
            reserva.fin = cleaned_data['fin_calculado']
            
            try:
                reserva.save()
                messages.success(request, 'Reserva creada correctamente.')
                return redirect('confirmacion_reserva')
            except Exception as e:
                messages.error(request, 'Error al guardar la reserva. Inténtalo de nuevo.')
        else:
            # Los errores del formulario se mostrarán automáticamente en el template
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = ReservaForm(initial=initial_data)
    
    return render(request, 'crearReserva.html', {'form': form})