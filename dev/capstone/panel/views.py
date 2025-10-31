from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta, date
import json
import csv

from agendabarber.models import Reserva, Servicio, Barbero
from .analytics_service import AnalyticsService

def admin_required(view_func):
    """
    Decorador para verificar permisos administrativos
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Verificar si es superuser o barbero
        is_admin = request.user.is_superuser
        is_barbero = False
        
        try:
            Barbero.objects.get(usuario=request.user)
            is_barbero = True
        except Barbero.DoesNotExist:
            pass
        
        if not (is_admin or is_barbero):
            messages.error(request, 'No tienes permisos para acceder al panel administrativo.')
            return redirect('inicio')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

@admin_required
def dashboard(request):
    """
    Vista principal del dashboard administrativo
    Basada en tu código inicial pero expandida con más métricas
    """
    # Obtener período de filtro (por defecto: mes actual)
    period = request.GET.get('period', 'this_month')
    start_date, end_date = get_date_range(period)
    
    # Determinar si el usuario es barbero específico
    barbero_id = None
    try:
        barbero = Barbero.objects.get(usuario=request.user)
        barbero_id = barbero.id
    except Barbero.DoesNotExist:
        pass
    
    # Métricas principales usando el servicio de analytics
    revenue_metrics = AnalyticsService.get_revenue_metrics(
        start_date=start_date, 
        end_date=end_date, 
        barbero_id=barbero_id
    )
    
    booking_stats = AnalyticsService.get_booking_statistics(
        start_date=start_date, 
        end_date=end_date, 
        barbero_id=barbero_id
    )
    
    # Top 5 servicios más populares (tu código original adaptado)
    top_servicios_query = Servicio.objects.annotate(
        total=Count('reserva', filter=Q(
            reserva__inicio__date__gte=start_date,
            reserva__inicio__date__lte=end_date
        ) if start_date and end_date else Q())
    ).order_by('-total')[:5]
    
    # Si es barbero específico, filtrar por sus reservas
    if barbero_id:
        top_servicios_query = top_servicios_query.filter(
            reserva__barbero_id=barbero_id
        )
    
    top_servicios = list(top_servicios_query)
    
    # Datos para gráficos (se cargarán vía AJAX)
    context = {
        # Métricas principales
        'total_ingresos': revenue_metrics['total_revenue'],
        'total_reservas': revenue_metrics['total_bookings'],
        'valor_promedio': revenue_metrics['avg_booking_value'],
        'tasa_completacion': booking_stats['completion_rate'],
        
        # Servicios populares
        'top_servicios': top_servicios,
        
        # Filtros
        'period': period,
        'start_date': start_date.isoformat() if start_date else '',
        'end_date': end_date.isoformat() if end_date else '',
        
        # Info del usuario
        'is_barbero': barbero_id is not None,
        'barbero_id': barbero_id,
    }
    
    return render(request, 'panel/dashboard.html', context)

@admin_required
def revenue_data_api(request):
    """
    API endpoint para datos de ingresos (para gráficos)
    """
    period = request.GET.get('period', 'this_month')
    start_date, end_date = get_date_range(period)
    
    # Determinar barbero si aplica
    barbero_id = None
    try:
        barbero = Barbero.objects.get(usuario=request.user)
        barbero_id = barbero.id
    except Barbero.DoesNotExist:
        pass
    
    # Obtener datos de tendencia mensual
    if period in ['this_year', 'last_year']:
        year = start_date.year if start_date else timezone.now().year
        monthly_data = AnalyticsService.get_monthly_revenue_trend(year)
        
        return JsonResponse({
            'labels': [item['month'] for item in monthly_data],
            'data': [item['revenue'] for item in monthly_data],
            'type': 'monthly'
        })
    
    # Para períodos más cortos, agrupar por días
    daily_data = []
    current_date = start_date
    
    while current_date <= end_date:
        revenue = Reserva.objects.filter(
            inicio__date=current_date,
            estado='Completada',
            pagado=True
        )
        
        if barbero_id:
            revenue = revenue.filter(barbero_id=barbero_id)
        
        daily_revenue = revenue.aggregate(total=Sum('servicio__precio'))['total'] or 0
        
        daily_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'revenue': daily_revenue
        })
        
        current_date += timedelta(days=1)
    
    return JsonResponse({
        'labels': [item['date'] for item in daily_data],
        'data': [item['revenue'] for item in daily_data],
        'type': 'daily'
    })

@admin_required
def booking_analytics_api(request):
    """
    API endpoint para estadísticas de reservas
    """
    period = request.GET.get('period', 'this_month')
    start_date, end_date = get_date_range(period)
    
    barbero_id = None
    try:
        barbero = Barbero.objects.get(usuario=request.user)
        barbero_id = barbero.id
    except Barbero.DoesNotExist:
        pass
    
    booking_stats = AnalyticsService.get_booking_statistics(
        start_date=start_date,
        end_date=end_date,
        barbero_id=barbero_id
    )
    
    peak_hours = AnalyticsService.get_peak_hours_analysis(
        start_date=start_date,
        end_date=end_date
    )
    
    return JsonResponse({
        'status_distribution': booking_stats['status_distribution'],
        'weekday_distribution': booking_stats['weekday_distribution'],
        'peak_hours': peak_hours,
        'completion_rate': booking_stats['completion_rate']
    })

@admin_required
def barber_performance_api(request):
    """
    API endpoint para rendimiento de barberos
    """
    period = request.GET.get('period', 'this_month')
    start_date, end_date = get_date_range(period)
    
    performance_data = AnalyticsService.get_barber_performance(
        start_date=start_date,
        end_date=end_date
    )
    
    return JsonResponse({
        'barber_performance': performance_data
    })

@admin_required
def service_analytics_api(request):
    """
    API endpoint para análisis de servicios
    """
    period = request.GET.get('period', 'this_month')
    start_date, end_date = get_date_range(period)
    
    service_data = AnalyticsService.get_service_popularity(
        start_date=start_date,
        end_date=end_date
    )
    
    return JsonResponse({
        'service_popularity': service_data
    })

@admin_required
def export_report(request):
    """
    Exportar reporte en CSV
    """
    period = request.GET.get('period', 'this_month')
    format_type = request.GET.get('format', 'csv')
    start_date, end_date = get_date_range(period)
    
    barbero_id = None
    try:
        barbero = Barbero.objects.get(usuario=request.user)
        barbero_id = barbero.id
    except Barbero.DoesNotExist:
        pass
    
    if format_type == 'csv':
        return export_csv_report(start_date, end_date, barbero_id, period)
    
    # TODO: Implementar exportación PDF en futuras iteraciones
    messages.error(request, 'Formato de exportación no soportado aún.')
    return redirect('dashboard')

def export_csv_report(start_date, end_date, barbero_id, period):
    """
    Genera reporte CSV
    """
    try:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f'reporte_barberia_{period}_{date.today().isoformat()}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Headers
        writer.writerow(['Reporte de Barbería', f'Período: {period}'])
        writer.writerow(['Fecha de generación:', date.today().isoformat()])
        if start_date and end_date:
            writer.writerow(['Rango de fechas:', f'{start_date.isoformat()} a {end_date.isoformat()}'])
        writer.writerow([])  # Línea vacía
        
        # Métricas principales
        revenue_metrics = AnalyticsService.get_revenue_metrics(
            start_date=start_date,
            end_date=end_date,
            barbero_id=barbero_id
        )
        
        writer.writerow(['MÉTRICAS PRINCIPALES'])
        writer.writerow(['Total Ingresos', f'${revenue_metrics["total_revenue"]}'])
        writer.writerow(['Total Reservas', revenue_metrics['total_bookings']])
        writer.writerow(['Valor Promedio', f'${revenue_metrics["avg_booking_value"]}'])
        writer.writerow([])
        
        # Servicios populares
        service_data = AnalyticsService.get_service_popularity(
            start_date=start_date,
            end_date=end_date
        )
        
        writer.writerow(['SERVICIOS MÁS POPULARES'])
        writer.writerow(['Servicio', 'Total Reservas', 'Ingresos Totales'])
        
        if service_data:
            for service in service_data[:10]:  # Top 10
                writer.writerow([
                    service.get('servicio__nombre', 'N/A'),
                    service.get('total_bookings', 0),
                    f"${service.get('total_revenue', 0) or 0}"
                ])
        else:
            writer.writerow(['No hay datos disponibles para el período seleccionado'])
        
        return response
        
    except Exception as e:
        # En caso de error, devolver respuesta de error
        response = HttpResponse(f'Error al generar el reporte: {str(e)}', status=500)
        return response

def get_date_range(period):
    """
    Convierte período en rango de fechas
    """
    today = date.today()
    
    if period == 'last_7_days':
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == 'last_30_days':
        start_date = today - timedelta(days=30)
        end_date = today
    elif period == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'last_month':
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        start_date = last_day_last_month.replace(day=1)
        end_date = last_day_last_month
    elif period == 'this_year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:  # Default to this month
        start_date = today.replace(day=1)
        end_date = today
    
    return start_date, end_date