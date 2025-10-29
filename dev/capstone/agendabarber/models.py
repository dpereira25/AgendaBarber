from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta

# Define los estados posibles de una reserva para mejor control
ESTADO_CHOICES = [
    ('Pendiente', 'Pendiente'),
    ('Confirmada', 'Confirmada'),
    ('Cancelada', 'Cancelada'),
    ('Completada', 'Completada'),
]

# Define los días de la semana
DIA_CHOICES = [
    (1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'), 
    (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo')
]

class Barbero(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, 
                                   help_text="Usuario asociado a este barbero")
    nombre = models.CharField(max_length=100)
    experiencia = models.PositiveIntegerField(help_text="Años de experiencia")
    foto = models.ImageField(upload_to='barberos/', null=True, blank=True)

    def __str__(self):
        return self.nombre
    
    @property
    def es_usuario_barbero(self):
        """Verifica si tiene un usuario asociado"""
        return self.usuario is not None

class Servicio(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio = models.PositiveIntegerField()
    
    # 💡 CAMBIADO: La duración predeterminada es ahora 60 minutos (1 hora).
    duracion_minutos = models.PositiveIntegerField(
        default=60, 
        help_text="Duración del servicio en minutos"
    )
    imagen = models.ImageField(upload_to='servicios/', null=True, blank=True)

    def __str__(self):
        return self.nombre

class HorarioTrabajo(models.Model):
    barbero = models.ForeignKey(Barbero, on_delete=models.CASCADE)
    dia_semana = models.PositiveSmallIntegerField(choices=DIA_CHOICES)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    
    class Meta:
        unique_together = ('barbero', 'dia_semana') 

    def __str__(self):
        return f"{self.barbero.nombre} - {self.get_dia_semana_display()}: {self.hora_inicio.isoformat()} a {self.hora_fin.isoformat()}"


class Reserva(models.Model):
    cliente = models.ForeignKey(User, on_delete=models.CASCADE)
    barbero = models.ForeignKey(Barbero, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    
    inicio = models.DateTimeField(help_text="Hora de inicio de la reserva")
    fin = models.DateTimeField(null=True, blank=True)
    
    pagado = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')

    def save(self, *args, **kwargs):
        # Solo calcular fin si no está establecido (para mantener compatibilidad)
        if self.servicio and self.inicio and not self.fin:
            self.fin = self.inicio + timedelta(minutes=self.servicio.duracion_minutos)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente.username} - {self.inicio.isoformat()}"