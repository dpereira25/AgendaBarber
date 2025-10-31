from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/revenue-data/', views.revenue_data_api, name='revenue_data_api'),
    path('api/booking-analytics/', views.booking_analytics_api, name='booking_analytics_api'),
    path('api/barber-performance/', views.barber_performance_api, name='barber_performance_api'),
    path('api/service-analytics/', views.service_analytics_api, name='service_analytics_api'),
    path('export/', views.export_report, name='export_report'),
]