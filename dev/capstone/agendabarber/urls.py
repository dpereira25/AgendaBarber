from django.urls import path
from . import views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('', views.cargarBase),
    path('catalogo', views.cargarCatalogo),
    path('crearReserva', views.crearReserva),
    path('inicio', views.cargarInicio),
    path('confirmacionReserva', views.confirmacionReserva),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)