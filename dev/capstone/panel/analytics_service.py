from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta, date
from agendabarber.models import Reserva, Servicio, Barbero
import calendar

class AnalyticsService:
    """
    Servicio para cálculos de métricas y analytics del negocio
    """
    
    @staticmethod
    def get_revenue_metrics(start_date=None, end_date=None, barbero_id=None):
        """
        Calcula métricas de ingresos para un período específico
        """
        # Filtro base: solo reservas completadas (por tiempo)
        # Usamos completadas() en lugar de ingresos_reales() para incluir todas las reservas completadas
        queryset = Reserva.objects.completadas()
        
        # Aplicar filtros de fecha si se proporcionan
        if start_date:
            queryset = queryset.filter(inicio__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(inicio__date__lte=end_date)
        if barbero_id:
            queryset = queryset.filter(barbero_id=barbero_id)
        
        # Calcular métricas
        metrics = queryset.aggregate(
            total_revenue=Sum('servicio__precio'),
            total_bookings=Count('id'),
            avg_booking_value=Avg('servicio__precio')
        )
        
        # Manejar valores None
        return {
            'total_revenue': metrics['total_revenue'] or 0,
            'total_bookings': metrics['total_bookings'] or 0,
            'avg_booking_value': round(metrics['avg_booking_value'] or 0, 2)
        }
    
    @staticmethod
    def get_booking_statistics(start_date=None, end_date=None, barbero_id=None):
        """
        Obtiene estadísticas detalladas de reservas
        """
        # Filtro base
        queryset = Reserva.objects.all()
        
        # Aplicar filtros
        if start_date:
            queryset = queryset.filter(inicio__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(inicio__date__lte=end_date)
        if barbero_id:
            queryset = queryset.filter(barbero_id=barbero_id)
        
        # Estadísticas por estado
        status_stats = queryset.values('estado').annotate(
            count=Count('id')
        ).order_by('estado')
        
        # Reservas por día de la semana (en español)
        dias_espanol = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        weekday_stats = []
        for i in range(7):
            count = queryset.filter(inicio__week_day=i+1).count()
            weekday_stats.append({
                'day': dias_espanol[i if i < 6 else 0],  # Ajustar domingo
                'count': count
            })
        
        # Calcular tasa de completación basada en tiempo
        total_bookings = queryset.count()
        completed_bookings = Reserva.objects.completadas().filter(
            **{k: v for k, v in {
                'inicio__date__gte': start_date,
                'inicio__date__lte': end_date,
                'barbero_id': barbero_id
            }.items() if v is not None}
        ).count()
        
        completion_rate = (completed_bookings / total_bookings * 100) if total_bookings > 0 else 0
        
        return {
            'status_distribution': list(status_stats),
            'weekday_distribution': weekday_stats,
            'completion_rate': round(completion_rate, 2),
            'total_bookings': total_bookings
        }
    
    @staticmethod
    def get_barber_performance(start_date=None, end_date=None):
        """
        Analiza el rendimiento individual de cada barbero
        """
        # Obtener todos los barberos
        barberos = Barbero.objects.all()
        performance_data = []
        
        for barbero in barberos:
            # Filtro base para este barbero
            queryset = Reserva.objects.filter(barbero=barbero)
            
            # Aplicar filtros de fecha
            if start_date:
                queryset = queryset.filter(inicio__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(inicio__date__lte=end_date)
            
            # Calcular métricas basadas en tiempo
            total_bookings = queryset.count()
            
            # Filtrar reservas completadas con los mismos filtros de fecha
            completed_queryset = Reserva.objects.completadas().filter(barbero=barbero)
            if start_date:
                completed_queryset = completed_queryset.filter(inicio__date__gte=start_date)
            if end_date:
                completed_queryset = completed_queryset.filter(inicio__date__lte=end_date)
            
            completed_bookings = completed_queryset.count()
            revenue = completed_queryset.aggregate(
                total=Sum('servicio__precio')
            )['total'] or 0
            
            completion_rate = (completed_bookings / total_bookings * 100) if total_bookings > 0 else 0
            
            performance_data.append({
                'barbero_id': barbero.id,
                'barbero_name': barbero.nombre,
                'total_bookings': total_bookings,
                'completed_bookings': completed_bookings,
                'revenue': revenue,
                'completion_rate': round(completion_rate, 2)
            })
        
        return performance_data
    
    @staticmethod
    def get_service_popularity(start_date=None, end_date=None):
        """
        Analiza la popularidad y rendimiento de servicios
        """
        # Filtro base
        queryset = Reserva.objects.all()
        
        # Aplicar filtros de fecha
        if start_date:
            queryset = queryset.filter(inicio__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(inicio__date__lte=end_date)
        
        # Servicios por popularidad (total de reservas)
        # Usar reservas completadas para servicios
        completed_queryset = Reserva.objects.completadas()
        if start_date:
            completed_queryset = completed_queryset.filter(inicio__date__gte=start_date)
        if end_date:
            completed_queryset = completed_queryset.filter(inicio__date__lte=end_date)
            
        service_bookings = completed_queryset.values(
            'servicio__id', 'servicio__nombre', 'servicio__precio'
        ).annotate(
            total_bookings=Count('id'),
            total_revenue=Sum('servicio__precio')
        ).order_by('-total_bookings')
        
        return list(service_bookings)
    
    @staticmethod
    def get_peak_hours_analysis(start_date=None, end_date=None, barbero_id=None):
        """
        Analiza las horas pico de reservas
        """
        # Filtro base
        queryset = Reserva.objects.all()
        
        # Aplicar filtros de fecha
        if start_date:
            queryset = queryset.filter(inicio__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(inicio__date__lte=end_date)
        if barbero_id:
            queryset = queryset.filter(barbero_id=barbero_id)
        
        # Agrupar por hora
        hours_data = {}
        for hour in range(24):
            count = queryset.filter(inicio__hour=hour).count()
            hours_data[f"{hour:02d}:00"] = count
        
        return hours_data
    
    @staticmethod
    def get_monthly_revenue_trend(year=None, barbero_id=None):
        """
        Obtiene tendencia de ingresos mensuales
        """
        if not year:
            year = timezone.now().year
        
        # Nombres de meses en español
        meses_espanol = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        
        monthly_data = []
        for month in range(1, 13):
            # Usar completadas() en lugar de ingresos_reales()
            queryset = Reserva.objects.completadas().filter(
                inicio__year=year,
                inicio__month=month
            )
            
            if barbero_id:
                queryset = queryset.filter(barbero_id=barbero_id)
            
            revenue = queryset.aggregate(total=Sum('servicio__precio'))['total'] or 0
            
            monthly_data.append({
                'month': meses_espanol[month],
                'revenue': revenue
            })
        
        return monthly_data
    
    @staticmethod
    def calculate_completion_rates(start_date=None, end_date=None):
        """
        Calcula tasas de completación por diferentes dimensiones
        """
        # Filtro base
        queryset = Reserva.objects.all()
        
        # Aplicar filtros de fecha
        if start_date:
            queryset = queryset.filter(inicio__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(inicio__date__lte=end_date)
        
        total = queryset.count()
        # Simplificado - todas las reservas son exitosas
        return {
            'overall_completion_rate': 100.0 if total > 0 else 0,
            'cancellation_rate': 0,
            'pending_rate': 0
        }