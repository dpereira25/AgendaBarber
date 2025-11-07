"""
Service for checking availability of time slots considering both regular and temporary reservations.
"""

from django.utils import timezone
from datetime import datetime, timedelta, time, date
from ..models import Reserva, TemporaryReservation, Barbero, HorarioTrabajo
import logging

logger = logging.getLogger(__name__)


class AvailabilityService:
    """Service class for checking time slot availability"""
    
    @classmethod
    def is_time_slot_available(cls, barbero, inicio, fin, exclude_temp_reservation_id=None):
        """
        Check if a time slot is available for booking.
        
        Args:
            barbero: Barbero instance
            inicio (datetime): Start time of the slot
            fin (datetime): End time of the slot
            exclude_temp_reservation_id: UUID to exclude from temp reservation check (for updates)
            
        Returns:
            bool: True if available, False if blocked
        """
        # Check for existing confirmed reservations
        existing_reservas = Reserva.objects.filter(
            barbero=barbero,
            inicio__lt=fin,
            fin__gt=inicio,
            estado__in=['Pendiente', 'Confirmada']
        ).exists()
        
        if existing_reservas:
            return False
        
        # Check for active temporary reservations
        temp_query = TemporaryReservation.objects.active().filter(
            barbero=barbero,
            inicio__lt=fin,
            fin__gt=inicio
        )
        
        # Exclude specific temporary reservation if provided (for updates)
        if exclude_temp_reservation_id:
            temp_query = temp_query.exclude(id=exclude_temp_reservation_id)
        
        temp_reservations = temp_query.exists()
        
        return not temp_reservations
    
    @classmethod
    def get_available_hours_for_date(cls, barbero, fecha, formato='simple'):
        """
        Get all available hours for a barbero on a specific date.
        
        Args:
            barbero: Barbero instance
            fecha (date): Date to check availability
            formato (str): 'simple' or 'completo' for response format
            
        Returns:
            list: Available time slots
        """
        # Get working hours for the barbero on this day
        dia_semana = fecha.isoweekday()
        
        try:
            horario = HorarioTrabajo.objects.get(barbero=barbero, dia_semana=dia_semana)
            hora_inicio = horario.hora_inicio
            hora_fin = horario.hora_fin
        except HorarioTrabajo.DoesNotExist:
            # Use default schedule
            if 1 <= dia_semana <= 5:  # Monday to Friday
                hora_inicio = time(18, 0)
                hora_fin = time(21, 0)
            elif dia_semana == 6:  # Saturday
                hora_inicio = time(9, 0)
                hora_fin = time(18, 0)
            else:  # Sunday
                return []
        
        # Generate available hours (every hour)
        horas_disponibles = []
        datetime_inicio = datetime.combine(fecha, hora_inicio)
        datetime_fin = datetime.combine(fecha, hora_fin)
        
        hora_actual = datetime_inicio
        while hora_actual < datetime_fin:
            # Check if this hour is available
            inicio_slot = timezone.make_aware(hora_actual)
            fin_slot = inicio_slot + timedelta(hours=1)
            
            if cls.is_time_slot_available(barbero, inicio_slot, fin_slot):
                hora_data = {
                    'value': hora_actual.time().strftime('%H:%M'),
                    'text': hora_actual.time().strftime('%H:%M')
                }
                
                # Add additional information for complete format
                if formato == 'completo':
                    hora_data['datetime'] = inicio_slot.isoformat()
                
                horas_disponibles.append(hora_data)
            
            # Advance 1 hour
            hora_actual += timedelta(hours=1)
        
        return horas_disponibles
    
    @classmethod
    def get_blocked_slots_for_date(cls, barbero, fecha):
        """
        Get all blocked time slots for a barbero on a specific date.
        
        Args:
            barbero: Barbero instance
            fecha (date): Date to check
            
        Returns:
            dict: Contains 'reservas' and 'temporary' lists with blocked slots
        """
        # Get confirmed reservations
        reservas = Reserva.objects.filter(
            barbero=barbero,
            inicio__date=fecha,
            estado__in=['Pendiente', 'Confirmada']
        ).values('inicio', 'fin', 'cliente__username', 'servicio__nombre')
        
        # Get active temporary reservations
        temp_reservations = TemporaryReservation.objects.active().filter(
            barbero=barbero,
            inicio__date=fecha
        ).values('inicio', 'fin', 'cliente_email', 'servicio__nombre', 'expires_at')
        
        return {
            'reservas': list(reservas),
            'temporary': list(temp_reservations)
        }
    
    @classmethod
    def cleanup_and_get_availability(cls, barbero, fecha, formato='simple'):
        """
        Clean up expired temporary reservations and then get availability.
        
        Args:
            barbero: Barbero instance
            fecha (date): Date to check availability
            formato (str): 'simple' or 'completo' for response format
            
        Returns:
            list: Available time slots after cleanup
        """
        # Clean up expired temporary reservations first
        expired_count = TemporaryReservation.objects.cleanup_expired()
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired temporary reservations")
        
        # Return availability
        return cls.get_available_hours_for_date(barbero, fecha, formato)
    
    @classmethod
    def is_barbero_available_on_date(cls, barbero, fecha):
        """
        Check if a barbero works on a specific date.
        
        Args:
            barbero: Barbero instance
            fecha (date): Date to check
            
        Returns:
            bool: True if barbero works on this date
        """
        dia_semana = fecha.isoweekday()
        
        # Check if barbero has working hours for this day
        has_schedule = HorarioTrabajo.objects.filter(
            barbero=barbero, 
            dia_semana=dia_semana
        ).exists()
        
        if has_schedule:
            return True
        
        # Check default schedule
        if 1 <= dia_semana <= 6:  # Monday to Saturday
            return True
        
        return False  # Sunday
    
    @classmethod
    def get_next_available_slot(cls, barbero, servicio, from_datetime=None):
        """
        Find the next available time slot for a service with a barbero.
        
        Args:
            barbero: Barbero instance
            servicio: Servicio instance
            from_datetime: Start searching from this datetime (default: now)
            
        Returns:
            datetime or None: Next available start time
        """
        if from_datetime is None:
            from_datetime = timezone.now()
        
        # Search for up to 30 days
        search_date = from_datetime.date()
        end_date = search_date + timedelta(days=30)
        
        while search_date <= end_date:
            if cls.is_barbero_available_on_date(barbero, search_date):
                available_hours = cls.get_available_hours_for_date(barbero, search_date)
                
                for hour_data in available_hours:
                    slot_time = datetime.strptime(hour_data['value'], '%H:%M').time()
                    slot_datetime = timezone.make_aware(datetime.combine(search_date, slot_time))
                    
                    # Skip if this slot is in the past
                    if slot_datetime <= from_datetime:
                        continue
                    
                    # Check if the full service duration fits
                    slot_end = slot_datetime + timedelta(minutes=servicio.duracion_minutos)
                    
                    if cls.is_time_slot_available(barbero, slot_datetime, slot_end):
                        return slot_datetime
            
            search_date += timedelta(days=1)
        
        return None