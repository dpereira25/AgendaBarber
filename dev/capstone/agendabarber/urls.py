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
    
    # Rutas del proceso de reserva
    # Formulario principal unificado
    path('reservar/', views.crearReserva, name='crear_reserva'),
    
    # Página de confirmación
    path('reservar/confirmacion/', views.confirmacionReserva, name='confirmacion_reserva'),
    
    # Vista AJAX para obtener horas disponibles
    path('api/horas-disponibles/', views.obtener_horas_disponibles, name='horas_disponibles'),
    
    # Vistas de reservas
    path('mis-reservas/', views.mis_reservas_cliente, name='mis_reservas'),
    path('agenda-barbero/', views.agenda_barbero, name='agenda_barbero'),
    
    # Acciones de reservas
    path('cancelar-reserva/', views.cancelar_reserva, name='cancelar_reserva'),
    
    path('auth/registro/', views.registro_usuario, name='registro'),
]

# Configuración de archivos estáticos y media (fotos de barberos/servicios) en entorno de desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)