from django.db import models
from django.contrib.auth.models import User
# Create your models here.



class Barbero(models.Model):
    nombre = models.CharField(max_length=100)
    experiencia = models.PositiveIntegerField(help_text="Años de experiencia")
    foto = models.ImageField(upload_to='barberos/', null=True, blank=True)

    def __str__(self):
        return self.nombre

class Servicio(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio = models.PositiveIntegerField()
    imagen = models.ImageField(upload_to='servicios/', null=True, blank=True)

    def __str__(self):
        return self.nombre

class Reserva(models.Model):
    cliente = models.ForeignKey(User, on_delete=models.CASCADE)
    barbero = models.ForeignKey(Barbero, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    fecha = models.DateField()
    hora = models.TimeField()
    pagado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cliente.username} - {self.fecha} {self.hora}"
