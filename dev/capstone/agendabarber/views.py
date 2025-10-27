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

# ----------------------------------------------------------------------
# FUNCIÓN PARA SELECCIONAR SLOTS (Se mantiene)
# ----------------------------------------------------------------------
def seleccionar_slot(request):
    # ... (Toda tu lógica de seleccionar_slot se mantiene exactamente igual) ...
    if request.method == 'POST':
        barbero_id = request.POST.get('barbero')
        servicio_id = request.POST.get('servicio')
        fecha_str = request.POST.get('fecha')
        
        if not all([barbero_id, servicio_id, fecha_str]):
            messages.error(request, "Por favor, selecciona un barbero, servicio y fecha.")
            return render(request, 'seleccionar_filtros.html', {'barberos': Barbero.objects.all(), 'servicios': Servicio.objects.all()})
            
        try:
            barbero = get_object_or_404(Barbero, pk=barbero_id)
            servicio = get_object_or_404(Servicio, pk=servicio_id)
            fecha_reserva = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Formato de fecha inválido.")
            return redirect('inicio') 
        
        dia_semana = fecha_reserva.isoweekday() 
        
        if 1 <= dia_semana <= 5: 
            horario = HORARIO_SEMANAL
        elif dia_semana == 6: 
            horario = HORARIO_SABADO
        else: 
            messages.error(request, f'La barbería está cerrada el día {fecha_reserva.strftime("%A")}.')
            return redirect('inicio')
        
        hora_inicio_laboral = timezone.make_aware(
            datetime.combine(fecha_reserva, horario['inicio'])
        )
        hora_fin_laboral = timezone.make_aware(
            datetime.combine(fecha_reserva, horario['fin'])
        )
        
        duracion_servicio = timedelta(minutes=servicio.duracion_minutos)
        
        slots_potenciales = []
        slot_actual = hora_inicio_laboral
        
        while slot_actual + duracion_servicio <= hora_fin_laboral:
            slots_potenciales.append(slot_actual)
            slot_actual += duracion_servicio 

        reservas_ocupadas = Reserva.objects.filter(
            barbero=barbero,
            inicio__date=fecha_reserva,
            estado__in=['Pendiente', 'Confirmada'] 
        ).order_by('inicio')
        
        slots_disponibles = []
        
        for slot in slots_potenciales:
            slot_fin = slot + duracion_servicio
            esta_ocupado = False
            
            for reserva in reservas_ocupadas:
                if reserva.inicio < slot_fin and reserva.fin > slot:
                    esta_ocupado = True
                    break 
            
            if not esta_ocupado:
                slots_disponibles.append(slot)
        
        context = {
            'barbero': barbero,
            'servicio': servicio,
            'fecha_seleccionada': fecha_reserva,
            'slots_disponibles': slots_disponibles,
        }
        
        return render(request, 'slots_disponibles.html', context)
        
    else:
        context = {
            'barberos': Barbero.objects.all(),
            'servicios': Servicio.objects.all(),
        }
        return render(request, 'seleccionar_filtros.html', context)


# ----------------------------------------------------------------------
# 💡 FUNCIÓN DE CREACIÓN DE RESERVA (Actualizada con @login_required)
# ----------------------------------------------------------------------

@login_required # 1. Añadimos el decorador
def crearReserva(request):
    if request.method == 'POST':
        form = ReservaForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            
            # 2. Eliminamos el 'if not request.user.is_authenticated'
            #    El decorador @login_required ya lo maneja.
            #    Si el usuario no está logueado, será redirigido a 'login' (definido en settings.py).
            
            # 3. Asignamos el usuario logueado
            reserva.cliente = request.user
            
            servicio = reserva.servicio
            barbero = reserva.barbero
            
            duracion = timedelta(minutes=servicio.duracion_minutos) 
            inicio_reserva = reserva.inicio 
            fin_reserva = inicio_reserva + duracion

            # ... (Toda tu lógica de validación de horario fijo se mantiene) ...
            dia_semana = inicio_reserva.isoweekday() 
            if 1 <= dia_semana <= 5: 
                horario = HORARIO_SEMANAL
            elif dia_semana == 6: 
                horario = HORARIO_SABADO
            else: 
                messages.error(request, f'La barbería está cerrada los domingos.')
                return render(request, 'crearReserva.html', {'form': form})
            
            hora_inicio_laboral = timezone.make_aware(
                datetime.combine(inicio_reserva.date(), horario['inicio'])
            )
            hora_fin_laboral = timezone.make_aware(
                datetime.combine(inicio_reserva.date(), horario['fin'])
            )

            if inicio_reserva < hora_inicio_laboral or fin_reserva > hora_fin_laboral:
                messages.error(request, f'La reserva está fuera del horario fijo establecido.')
                return render(request, 'crearReserva.html', {'form': form})

            # ... (Toda tu lógica de validación de solapamiento se mantiene) ...
            solapamientos = Reserva.objects.filter(
                barbero=barbero,
                inicio__date=inicio_reserva.date(), 
                inicio__lt=fin_reserva,
                fin__gt=inicio_reserva
            ).exists()

            if solapamientos:
                messages.error(request, 'Esta franja horaria ya está ocupada por otra reserva.')
            else:
                reserva.save()
                messages.success(request, 'Reserva creada correctamente.')
                return redirect('confirmacionReserva') 
    else:
        form = ReservaForm()
    
    return render(request, 'crearReserva.html', {'form': form})