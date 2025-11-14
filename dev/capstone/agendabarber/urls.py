from django.urls import path
from . import views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    # Rutas de navegación principal
    # Usamos 'inicio' como la ruta principal (/)
    path('', views.cargarInicio, name='inicio'), 
    path('base/', views.cargarBase, name='base'),
    path('catalogo/', views.cargarCatalogo, name='catalogo'),
    path('contacto/', views.contacto, name='contacto'),
    
    # Rutas del proceso de reserva
    # Formulario principal unificado
    path('reservar/', views.crearReserva, name='crear_reserva'),
    
    # Página de confirmación
    path('reservar/confirmacion/', views.confirmacionReserva, name='confirmacion_reserva'),
    
    # Vista AJAX para obtener horas disponibles
    path('horas-disponibles/', views.obtener_horas_disponibles_unified, name='horas_disponibles'),
    
    # Vista AJAX para obtener información del servicio
    path('info-servicio/', views.obtener_info_servicio, name='info_servicio'),
    

    
    # Vistas de perfil y reservas
    path('perfil/', views.perfil_cliente, name='perfil_cliente'),
    path('mis-reservas/', views.mis_reservas_cliente, name='mis_reservas'),
    path('agenda-barbero/', views.agenda_barbero, name='agenda_barbero'),
    
    # Acciones de reservas
    path('cancelar-reserva/', views.cancelar_reserva, name='cancelar_reserva'),
    
    # Autenticación
    path('auth/registro/', views.registro_usuario, name='registro'),
    path('auth/logout/', views.logout_usuario, name='logout'),
    
    # Payment callbacks and webhook
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/failure/', views.payment_failure, name='payment_failure'),
    path('payment/pending/', views.payment_pending, name='payment_pending'),
    path('payment/retry/', views.retry_payment, name='retry_payment'),
    path('webhooks/mercadopago/', views.mercadopago_webhook, name='mercadopago_webhook'),
    
    # Additional availability endpoint
    path('disponibilidad-detallada/', views.obtener_disponibilidad_detallada, name='disponibilidad_detallada'),
    path('cleanup-expired/', views.cleanup_expired_reservations, name='cleanup_expired'),
    
    # Payment details API
    path('api/reserva/<int:reserva_id>/payment-details/', views.reserva_payment_details, name='reserva_payment_details'),
    
    # Gestión de Barberos
    path('barberos/', views.gestionar_barberos, name='gestionar_barberos'),
    path('barberos/crear/', views.crear_barbero, name='crear_barbero'),
    path('barberos/<int:barbero_id>/editar/', views.editar_barbero, name='editar_barbero'),
    path('barberos/<int:barbero_id>/eliminar/', views.eliminar_barbero, name='eliminar_barbero'),
]

# Configuración de archivos estáticos y media (fotos de barberos/servicios) en entorno de desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)