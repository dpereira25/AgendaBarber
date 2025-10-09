from django.urls import path
from . import views

urlpatterns = [
    path('', views.cargarBase),
    path('catalogo', views.cargarCatalogo),
]
