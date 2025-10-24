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
    
    # Rutas del proceso de reserva (Flow de 3 pasos)
    # 1. Selección de filtros y cálculo de slots disponibles (Lógica de horarios fijos)
    path('reservar/slot/', views.seleccionar_slot, name='seleccionar_slot'),
    
    # 2. Creación final de la reserva (Recibe el slot seleccionado y lo guarda)
    path('reservar/crear/', views.crearReserva, name='crear_reserva'),
    
    # 3. Página de confirmación
    path('reservar/confirmacion/', views.confirmacionReserva, name='confirmacion_reserva'),
    
    path('auth/registro/', views.registro_usuario, name='registro'),
]

# Configuración de archivos estáticos y media (fotos de barberos/servicios) en entorno de desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)