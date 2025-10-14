from django.contrib import admin
from .models import Barbero, Servicio, Reserva

# Register your models here.

admin.site.register(Barbero)
admin.site.register(Servicio)
admin.site.register(Reserva)
