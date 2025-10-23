from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import ReservaForm
from .models import Reserva, Servicio, Barbero 
from datetime import timedelta, datetime, time
from django.utils import timezone
from django.db.models import Q 

# ----------------------------------------------------------------------
# 💡 REGLAS DE HORARIO FIJO (Definidas aquí temporalmente)
# ----------------------------------------------------------------------

# Días 1 (Lunes) a 5 (Viernes)
HORARIO_SEMANAL = {'inicio': time(18, 0), 'fin': time(21, 0)} 
# Día 6 (Sábado)
HORARIO_SABADO = {'inicio': time(9, 0), 'fin': time(18, 0)}
# Día 7 (Domingo) - Cerrado

# ----------------------------------------------------------------------
# FUNCIONES DE NAVEGACIÓN (Se mantienen)
# ----------------------------------------------------------------------

def cargarBase(request):
    return render(request, 'base.html')

def cargarCatalogo(request):
    servicios = Servicio.objects.all()
    return render(request, 'catalogo.html', {'servicios': servicios})

def cargarInicio(request):
    return render(request, 'inicio.html')

def confirmacionReserva(request):
    return render(request, 'confirmacionReserva.html')

# ----------------------------------------------------------------------
# FUNCIÓN PARA SELECCIONAR SLOTS DISPONIBLES (Horario Fijo)
# ----------------------------------------------------------------------

def seleccionar_slot(request):
    
    if request.method == 'POST':
        # Obtención de datos del formulario de selección de Barbero/Servicio/Fecha
        barbero_id = request.POST.get('barbero')
        servicio_id = request.POST.get('servicio')
        fecha_str = request.POST.get('fecha')
        
        # Validación de datos inicial
        if not all([barbero_id, servicio_id, fecha_str]):
            messages.error(request, "Por favor, selecciona un barbero, servicio y fecha.")
            # Redirigir al formulario inicial si faltan datos
            return render(request, 'seleccionar_filtros.html', {'barberos': Barbero.objects.all(), 'servicios': Servicio.objects.all()})
            
        try:
            barbero = get_object_or_404(Barbero, pk=barbero_id)
            servicio = get_object_or_404(Servicio, pk=servicio_id)
            fecha_reserva = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Formato de fecha inválido.")
            return redirect('inicio') # O la URL de tu formulario de inicio
        
        
        # ----------------------------------------------------------------------
        # 2. DETERMINAR HORAS LABORALES FIJAS
        # ----------------------------------------------------------------------
        
        dia_semana = fecha_reserva.isoweekday() # 1=Lunes a 7=Domingo
        
        if 1 <= dia_semana <= 5: # Lunes a Viernes
            horario = HORARIO_SEMANAL
        elif dia_semana == 6: # Sábado
            horario = HORARIO_SABADO
        else: # Domingo (Cerrado)
            messages.error(request, f'La barbería está cerrada el día {fecha_reserva.strftime("%A")}.')
            return redirect('inicio')
        
        # Convertir la hora de inicio y fin laboral a objetos datetime (con timezone)
        hora_inicio_laboral = timezone.make_aware(
            datetime.combine(fecha_reserva, horario['inicio'])
        )
        hora_fin_laboral = timezone.make_aware(
            datetime.combine(fecha_reserva, horario['fin'])
        )
        
        duracion_servicio = timedelta(minutes=servicio.duracion_minutos)
        
        # ----------------------------------------------------------------------
        # 3. GENERAR SLOTS DE TIEMPO POTENCIALES
        # ----------------------------------------------------------------------
        
        slots_potenciales = []
        slot_actual = hora_inicio_laboral
        
        # Generar slots que terminan antes o exactamente a la hora de fin laboral
        while slot_actual + duracion_servicio <= hora_fin_laboral:
            slots_potenciales.append(slot_actual)
            # Avanzar al siguiente slot según la duración del servicio
            slot_actual += duracion_servicio 

        # ----------------------------------------------------------------------
        # 4. FILTRAR SLOTS DISPONIBLES
        # ----------------------------------------------------------------------
        
        # Obtener las reservas que ya están ocupadas por ese barbero ese día
        reservas_ocupadas = Reserva.objects.filter(
            barbero=barbero,
            inicio__date=fecha_reserva,
            estado__in=['Pendiente', 'Confirmada'] 
        ).order_by('inicio')
        
        slots_disponibles = []
        
        for slot in slots_potenciales:
            slot_fin = slot + duracion_servicio
            esta_ocupado = False
            
            # Comprobar solapamiento: [Reserva.Inicio < Slot.Fin] AND [Reserva.Fin > Slot.Inicio]
            for reserva in reservas_ocupadas:
                if reserva.inicio < slot_fin and reserva.fin > slot:
                    esta_ocupado = True
                    break 
            
            if not esta_ocupado:
                slots_disponibles.append(slot)

        # ----------------------------------------------------------------------
        # 5. RENDERIZAR RESULTADOS
        # ----------------------------------------------------------------------
        
        context = {
            'barbero': barbero,
            'servicio': servicio,
            'fecha_seleccionada': fecha_reserva,
            'slots_disponibles': slots_disponibles,
        }
        
        return render(request, 'slots_disponibles.html', context)
        
    else:
        # Petición GET: Cargar datos para el formulario inicial
        context = {
            'barberos': Barbero.objects.all(),
            'servicios': Servicio.objects.all(),
        }
        return render(request, 'seleccionar_filtros.html', context)


# ----------------------------------------------------------------------
# FUNCIÓN DE CREACIÓN DE RESERVA (Ajustada para Horario Fijo)
# ----------------------------------------------------------------------

def crearReserva(request):
    if request.method == 'POST':
        form = ReservaForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            
            if not request.user.is_authenticated:
                messages.error(request, 'Debes iniciar sesión para hacer una reserva.')
                return redirect('login_url') 
                
            reserva.cliente = request.user
            
            servicio = reserva.servicio
            barbero = reserva.barbero
            
            # --- 1. CÁLCULO DE HORARIO DE FIN ---
            duracion = timedelta(minutes=servicio.duracion_minutos) 
            inicio_reserva = reserva.inicio 
            fin_reserva = inicio_reserva + duracion

            # ----------------------------------------------------------------------
            # --- 2. VALIDACIÓN DE HORARIO DE TRABAJO FIJO ---
            # ----------------------------------------------------------------------
            
            dia_semana = inicio_reserva.isoweekday() 
            
            if 1 <= dia_semana <= 5: # Lunes a Viernes
                horario = HORARIO_SEMANAL
            elif dia_semana == 6: # Sábado
                horario = HORARIO_SABADO
            else: # Domingo (Cerrado)
                messages.error(request, f'La barbería está cerrada los domingos.')
                return render(request, 'crearReserva.html', {'form': form})
            
            
            # Crear objetos datetime con la hora de inicio y fin del horario fijo
            hora_inicio_laboral = timezone.make_aware(
                datetime.combine(inicio_reserva.date(), horario['inicio'])
            )
            hora_fin_laboral = timezone.make_aware(
                datetime.combine(inicio_reserva.date(), horario['fin'])
            )

            # Verificar si la reserva completa está dentro del horario laboral fijo
            if inicio_reserva < hora_inicio_laboral or fin_reserva > hora_fin_laboral:
                messages.error(request, f'La reserva está fuera del horario fijo establecido.')
                return render(request, 'crearReserva.html', {'form': form})

            # ----------------------------------------------------------------------
            # --- 3. VALIDACIÓN DE SOLAPAMIENTO (Se mantiene) ---
            # ----------------------------------------------------------------------
            
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