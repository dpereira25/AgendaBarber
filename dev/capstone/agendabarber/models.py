from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import uuid

# Forzar importación de Pillow para Django
try:
    from PIL import Image
    import PIL
    # Forzar que Django detecte Pillow
    import django.core.files.images
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

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


class ReservaManager(models.Manager):
    """Manager personalizado para Reserva con métodos de filtrado inteligente"""
    
    def completadas(self):
        """Devuelve reservas que ya han terminado (hora pasada)"""
        ahora = timezone.now()
        return self.filter(fin__lt=ahora)
    
    def pendientes(self):
        """Devuelve reservas que aún no han terminado"""
        ahora = timezone.now()
        return self.filter(fin__gte=ahora)
    
    def ingresos_reales(self):
        """Devuelve solo las reservas que generan ingresos (completadas y pagadas)"""
        ahora = timezone.now()
        return self.filter(fin__lt=ahora, pagado=True)

class Reserva(models.Model):
    cliente = models.ForeignKey(User, on_delete=models.CASCADE)
    barbero = models.ForeignKey(Barbero, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    
    inicio = models.DateTimeField(help_text="Hora de inicio de la reserva")
    fin = models.DateTimeField(null=True, blank=True)
    
    pagado = models.BooleanField(default=False)  # Changed: Now requires payment confirmation
    payment_method = models.CharField(max_length=50, default='mercadopago', 
                                     help_text="Método de pago utilizado")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')  # Pendiente hasta que pase la hora
    
    objects = ReservaManager()  # Manager personalizado

    def save(self, *args, **kwargs):
        # Solo calcular fin si no está establecido (para mantener compatibilidad)
        if self.servicio and self.inicio and not self.fin:
            self.fin = self.inicio + timedelta(minutes=self.servicio.duracion_minutos)
        
        # Actualizar estado automáticamente basado en la hora
        self.actualizar_estado_automatico()
        
        super().save(*args, **kwargs)
    
    def actualizar_estado_automatico(self):
        """Actualiza el estado automáticamente basado en si la reserva ya pasó"""
        from django.utils import timezone
        
        if self.fin and timezone.now() > self.fin:
            # La reserva ya terminó, marcarla como completada
            self.estado = 'Completada'
        elif self.estado == 'Completada' and self.fin and timezone.now() <= self.fin:
            # La reserva aún no termina, volver a pendiente
            self.estado = 'Pendiente'
    
    @property
    def esta_completada(self):
        """Determina si la reserva está completada basado en la hora actual"""
        from django.utils import timezone
        return self.fin and timezone.now() > self.fin
    
    @property
    def estado_actual(self):
        """Devuelve el estado actual considerando la hora"""
        if self.esta_completada:
            return 'Completada'
        return self.estado

    def __str__(self):
        return f"{self.cliente.username} - {self.inicio.isoformat()}"


class TemporaryReservationManager(models.Manager):
    """Manager personalizado para TemporaryReservation con métodos de limpieza"""
    
    def expired(self):
        """Devuelve reservas temporales que han expirado"""
        return self.filter(expires_at__lt=timezone.now())
    
    def active(self):
        """Devuelve reservas temporales que aún están activas"""
        return self.filter(expires_at__gte=timezone.now())
    
    def cleanup_expired(self):
        """Elimina todas las reservas temporales expiradas"""
        expired_count = self.expired().count()
        self.expired().delete()
        return expired_count
    
    def is_slot_blocked(self, barbero, inicio, fin):
        """Verifica si un horario está bloqueado por una reserva temporal activa"""
        return self.active().filter(
            barbero=barbero,
            inicio__lt=fin,
            fin__gt=inicio
        ).exists()


class TemporaryReservation(models.Model):
    """
    Modelo para bloquear temporalmente horarios durante el proceso de pago.
    Se elimina automáticamente después de 15 minutos o cuando se completa el pago.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=40, help_text="Clave de sesión del usuario")
    barbero = models.ForeignKey(Barbero, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    inicio = models.DateTimeField(help_text="Hora de inicio de la reserva temporal")
    fin = models.DateTimeField(help_text="Hora de fin de la reserva temporal")
    cliente_email = models.EmailField(help_text="Email del cliente para la reserva")
    cliente_nombre = models.CharField(max_length=100, help_text="Nombre del cliente")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="Momento en que expira el bloqueo temporal")
    mp_preference_id = models.CharField(max_length=100, null=True, blank=True, 
                                       help_text="ID de preferencia de MercadoPago")
    
    objects = TemporaryReservationManager()
    
    class Meta:
        unique_together = ('barbero', 'inicio')
        indexes = [
            models.Index(fields=['expires_at']),
            models.Index(fields=['barbero', 'inicio']),
            models.Index(fields=['session_key']),
        ]
    
    def save(self, *args, **kwargs):
        # Calcular fin automáticamente si no está establecido
        if self.servicio and self.inicio and not self.fin:
            self.fin = self.inicio + timedelta(minutes=self.servicio.duracion_minutos)
        
        # Establecer tiempo de expiración (15 minutos desde creación)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=15)
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Verifica si la reserva temporal ha expirado"""
        return timezone.now() > self.expires_at
    
    @property
    def time_remaining(self):
        """Devuelve el tiempo restante antes de expirar"""
        if self.is_expired:
            return timedelta(0)
        return self.expires_at - timezone.now()
    
    def __str__(self):
        return f"Temp: {self.cliente_email} - {self.barbero.nombre} - {self.inicio.isoformat()}"


class PaymentTransaction(models.Model):
    """
    Modelo para rastrear transacciones de pago de MercadoPago.
    Mantiene el historial completo de pagos y su relación con reservas.
    """
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('authorized', 'Autorizado'),
        ('in_process', 'En Proceso'),
        ('in_mediation', 'En Mediación'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Cancelado'),
        ('refunded', 'Reembolsado'),
        ('charged_back', 'Contracargo'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Tarjeta de Crédito'),
        ('debit_card', 'Tarjeta de Débito'),
        ('bank_transfer', 'Transferencia Bancaria'),
        ('cash', 'Efectivo'),
        ('digital_wallet', 'Billetera Digital'),
        ('other', 'Otro'),
    ]
    
    # Relaciones
    reserva = models.OneToOneField(Reserva, on_delete=models.CASCADE, null=True, blank=True,
                                  related_name='payment_transaction',
                                  help_text="Reserva final creada después del pago exitoso")
    temp_reservation = models.ForeignKey(TemporaryReservation, on_delete=models.CASCADE, 
                                        null=True, blank=True,
                                        related_name='payment_transactions',
                                        help_text="Reserva temporal asociada")
    
    # Datos de MercadoPago
    mp_payment_id = models.CharField(max_length=100, unique=True, 
                                    help_text="ID único del pago en MercadoPago")
    mp_preference_id = models.CharField(max_length=100,
                                       help_text="ID de preferencia de MercadoPago")
    mp_merchant_order_id = models.CharField(max_length=100, null=True, blank=True,
                                           help_text="ID de orden comercial de MercadoPago")
    
    # Información del pago
    amount = models.DecimalField(max_digits=10, decimal_places=2,
                                help_text="Monto del pago")
    currency = models.CharField(max_length=3, default='CLP',
                               help_text="Moneda del pago")
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES,
                             help_text="Estado del pago en MercadoPago")
    status_detail = models.CharField(max_length=100, null=True, blank=True,
                                    help_text="Detalle del estado del pago")
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES,
                                     null=True, blank=True,
                                     help_text="Método de pago utilizado")
    payment_type = models.CharField(max_length=50, null=True, blank=True,
                                   help_text="Tipo de pago específico de MercadoPago")
    
    # Información adicional
    external_reference = models.CharField(max_length=100, null=True, blank=True,
                                         help_text="Referencia externa para tracking")
    description = models.TextField(null=True, blank=True,
                                  help_text="Descripción del pago")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    mp_date_created = models.DateTimeField(null=True, blank=True,
                                          help_text="Fecha de creación en MercadoPago")
    mp_date_approved = models.DateTimeField(null=True, blank=True,
                                           help_text="Fecha de aprobación en MercadoPago")
    
    class Meta:
        indexes = [
            models.Index(fields=['mp_payment_id']),
            models.Index(fields=['mp_preference_id']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    @property
    def is_successful(self):
        """Verifica si el pago fue exitoso"""
        return self.status in ['approved', 'authorized']
    
    @property
    def is_pending(self):
        """Verifica si el pago está pendiente"""
        return self.status in ['pending', 'in_process', 'in_mediation']
    
    @property
    def is_failed(self):
        """Verifica si el pago falló"""
        return self.status in ['rejected', 'cancelled']
    
    def __str__(self):
        return f"Payment {self.mp_payment_id} - {self.status} - ${self.amount}"


class PaymentWebhookLog(models.Model):
    """
    Modelo para auditar todas las notificaciones webhook recibidas de MercadoPago.
    Permite rastrear y debuggear problemas con las notificaciones.
    """
    WEBHOOK_TOPIC_CHOICES = [
        ('payment', 'Pago'),
        ('merchant_order', 'Orden Comercial'),
        ('plan', 'Plan'),
        ('subscription', 'Suscripción'),
        ('invoice', 'Factura'),
        ('point_integration_wh', 'Integración Point'),
        ('other', 'Otro'),
    ]
    
    PROCESSING_STATUS_CHOICES = [
        ('received', 'Recibido'),
        ('processing', 'Procesando'),
        ('processed', 'Procesado'),
        ('failed', 'Falló'),
        ('ignored', 'Ignorado'),
        ('duplicate', 'Duplicado'),
    ]
    
    # Información del webhook
    webhook_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False,
                                 help_text="ID único para este webhook log")
    topic = models.CharField(max_length=50, choices=WEBHOOK_TOPIC_CHOICES,
                            help_text="Tipo de notificación recibida")
    resource_id = models.CharField(max_length=100,
                                  help_text="ID del recurso notificado (payment_id, etc.)")
    
    # Datos de la request
    request_method = models.CharField(max_length=10, default='POST')
    request_headers = models.JSONField(default=dict,
                                      help_text="Headers HTTP de la request")
    request_body = models.JSONField(default=dict,
                                   help_text="Cuerpo de la request recibida")
    request_query_params = models.JSONField(default=dict,
                                           help_text="Parámetros de query de la URL")
    
    # Información de procesamiento
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES,
                                        default='received',
                                        help_text="Estado del procesamiento del webhook")
    processing_error = models.TextField(null=True, blank=True,
                                       help_text="Error ocurrido durante el procesamiento")
    processing_attempts = models.PositiveIntegerField(default=0,
                                                     help_text="Número de intentos de procesamiento")
    
    # Relación con transacción (si se pudo procesar)
    payment_transaction = models.ForeignKey(PaymentTransaction, on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           related_name='webhook_logs',
                                           help_text="Transacción de pago relacionada")
    
    # Información de red
    source_ip = models.GenericIPAddressField(null=True, blank=True,
                                            help_text="IP de origen del webhook")
    user_agent = models.TextField(null=True, blank=True,
                                 help_text="User-Agent del webhook")
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True,
                                      help_text="Momento en que se recibió el webhook")
    processed_at = models.DateTimeField(null=True, blank=True,
                                       help_text="Momento en que se procesó exitosamente")
    
    class Meta:
        indexes = [
            models.Index(fields=['topic', 'resource_id']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['received_at']),
            models.Index(fields=['source_ip']),
        ]
        ordering = ['-received_at']
    
    @property
    def is_processed_successfully(self):
        """Verifica si el webhook fue procesado exitosamente"""
        return self.processing_status == 'processed'
    
    @property
    def needs_retry(self):
        """Verifica si el webhook necesita ser reintentado"""
        return self.processing_status == 'failed' and self.processing_attempts < 3
    
    def mark_as_processed(self):
        """Marca el webhook como procesado exitosamente"""
        self.processing_status = 'processed'
        self.processed_at = timezone.now()
        self.save(update_fields=['processing_status', 'processed_at'])
    
    def mark_as_failed(self, error_message):
        """Marca el webhook como fallido con mensaje de error"""
        self.processing_status = 'failed'
        self.processing_error = error_message
        self.processing_attempts += 1
        self.save(update_fields=['processing_status', 'processing_error', 'processing_attempts'])
    
    def __str__(self):
        return f"Webhook {self.topic} - {self.resource_id} - {self.processing_status}"