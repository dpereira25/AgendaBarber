from django import forms
from django.utils import timezone
from datetime import datetime, timedelta, time, date
from .models import Reserva, Servicio, Barbero

class ReservaForm(forms.ModelForm):
    """
    Formulario para crear reservas
    """
    # Campos adicionales para fecha y hora separados
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'min': date.today().isoformat()
        }),
        label='Fecha de la reserva'
    )
    
    hora = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control'
        }),
        label='Hora de la reserva'
    )
    
    class Meta:
        model = Reserva
        fields = ['barbero', 'servicio', 'fecha', 'hora']
        widgets = {
            'barbero': forms.Select(attrs={'class': 'form-select'}),
            'servicio': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'barbero': 'Selecciona tu barbero',
            'servicio': 'Selecciona el servicio',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configurar queryset para barberos activos
        self.fields['barbero'].queryset = Barbero.objects.all()
        self.fields['servicio'].queryset = Servicio.objects.all()
        
        # Hacer campos requeridos
        self.fields['barbero'].required = True
        self.fields['servicio'].required = True
        self.fields['fecha'].required = True
        self.fields['hora'].required = True
    
    def clean_fecha(self):
        """
        Validar que la fecha no sea en el pasado
        """
        fecha = self.cleaned_data.get('fecha')
        if fecha and fecha < date.today():
            raise forms.ValidationError('No puedes reservar en una fecha pasada.')
        return fecha
    
    def clean_hora(self):
        """
        Validar que la hora esté dentro del horario de trabajo
        """
        hora = self.cleaned_data.get('hora')
        fecha = self.cleaned_data.get('fecha')
        
        if not hora:
            return hora
        
        # Determinar horario según el día
        if fecha:
            dia_semana = fecha.isoweekday()
            
            if dia_semana == 7:  # Domingo
                raise forms.ValidationError('No trabajamos los domingos.')
            elif 1 <= dia_semana <= 5:  # Lunes a viernes
                hora_inicio = time(18, 0)
                hora_fin = time(21, 0)
            elif dia_semana == 6:  # Sábado
                hora_inicio = time(9, 0)
                hora_fin = time(18, 0)
            else:
                raise forms.ValidationError('Día no válido.')
            
            if not (hora_inicio <= hora < hora_fin):
                if dia_semana == 6:
                    raise forms.ValidationError('Los sábados trabajamos de 9:00 a 18:00.')
                else:
                    raise forms.ValidationError('De lunes a viernes trabajamos de 18:00 a 21:00.')
        
        return hora
    
    def clean(self):
        """
        Validación general del formulario
        """
        cleaned_data = super().clean()
        fecha = cleaned_data.get('fecha')
        hora = cleaned_data.get('hora')
        barbero = cleaned_data.get('barbero')
        servicio = cleaned_data.get('servicio')
        
        if fecha and hora and barbero and servicio:
            # Crear datetime para la reserva
            inicio_datetime = timezone.make_aware(
                datetime.combine(fecha, hora)
            )
            
            # Calcular fin basado en la duración del servicio
            fin_datetime = inicio_datetime + timedelta(minutes=servicio.duracion_minutos)
            
            # Verificar si ya existe una reserva en ese horario para ese barbero
            reservas_existentes = Reserva.objects.filter(
                barbero=barbero,
                inicio__date=fecha,
                estado__in=['Pendiente', 'Confirmada']
            )
            
            for reserva in reservas_existentes:
                # Verificar solapamiento
                if (inicio_datetime < reserva.fin and fin_datetime > reserva.inicio):
                    raise forms.ValidationError(
                        f'El barbero {barbero.nombre} ya tiene una reserva en ese horario. '
                        f'Reserva existente: {reserva.inicio.strftime("%H:%M")} - {reserva.fin.strftime("%H:%M")}'
                    )
            
            # Agregar los valores calculados al cleaned_data
            cleaned_data['inicio_calculado'] = inicio_datetime
            cleaned_data['fin_calculado'] = fin_datetime
        
        return cleaned_data