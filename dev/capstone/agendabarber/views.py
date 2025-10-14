from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ReservaForm
from .models import Reserva
from .models import Servicio

# Create your views here.


#FUNCIONES PARA CARGAR VISTAS
def cargarBase(request):
    return render(request, 'base.html')


def cargarCatalogo(request):
    servicios = Servicio.objects.all()
    return render(request, 'catalogo.html', {'servicios': servicios})


def cargarInicio(request):
    return render(request, 'inicio.html')


#
def crearReserva(request):
    if request.method == 'POST':
        form = ReservaForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.cliente = request.user  # asignar usuario autenticado
            # validar si la hora ya está ocupada
            if Reserva.objects.filter(barbero=reserva.barbero, fecha=reserva.fecha, hora=reserva.hora).exists():
                messages.error(request, 'Esta hora ya está reservada.')
            else:
                reserva.save()
                messages.success(request, 'Reserva creada correctamente.')
                return redirect('/confirmacionReserva')
    else:
        form = ReservaForm()
    return render(request, 'crearReserva.html', {'form': form})

def confirmacionReserva(request):
    return render(request, 'confirmacionReserva.html')


