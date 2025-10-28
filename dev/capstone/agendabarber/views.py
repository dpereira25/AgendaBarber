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

from django.http import JsonResponse

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