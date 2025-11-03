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
    
    hora = forms.CharField(
        max_length=5,
        widget=forms.HiddenInput(attrs={
            'id': 'id_hora_hidden'
        }),
        label='Hora de la reserva',
        required=True
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
        Validar que la hora tenga el formato correcto
        """
        hora_str = self.cleaned_data.get('hora')
        
        if not hora_str:
            raise forms.ValidationError('Debes seleccionar una hora.')
        
        try:
            # Validar formato de hora
            datetime.strptime(hora_str, '%H:%M')
        except ValueError:
            raise forms.ValidationError('Formato de hora inválido.')
        
        return hora_str
    
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
            # Convertir hora string a time object
            try:
                hora_obj = datetime.strptime(hora, '%H:%M').time()
            except ValueError:
                raise forms.ValidationError('Formato de hora inválido.')
            
            # Verificar que la hora esté dentro del horario del barbero
            from .models import HorarioTrabajo
            dia_semana = fecha.isoweekday()
            
            # Verificar horario del barbero
            try:
                horario = HorarioTrabajo.objects.get(barbero=barbero, dia_semana=dia_semana)
                hora_inicio = horario.hora_inicio
                hora_fin = horario.hora_fin
            except HorarioTrabajo.DoesNotExist:
                # Usar horario por defecto
                if dia_semana == 7:  # Domingo
                    raise forms.ValidationError('No trabajamos los domingos.')
                elif 1 <= dia_semana <= 5:  # Lunes a viernes
                    hora_inicio = time(18, 0)
                    hora_fin = time(21, 0)
                elif dia_semana == 6:  # Sábado
                    hora_inicio = time(9, 0)
                    hora_fin = time(18, 0)
            
            # Verificar que la hora esté dentro del rango de trabajo
            if not (hora_inicio <= hora_obj < hora_fin):
                raise forms.ValidationError(f'La hora seleccionada está fuera del horario de trabajo.')
            
            # Crear datetime para la reserva
            inicio_datetime = timezone.make_aware(
                datetime.combine(fecha, hora_obj)
            )
            
            # Calcular fin basado en la duración del servicio
            fin_datetime = inicio_datetime + timedelta(minutes=servicio.duracion_minutos)
            
            # Verificar disponibilidad usando la misma lógica que la API
            fin_slot = inicio_datetime + timedelta(hours=1)
            
            ocupado = Reserva.objects.filter(
                barbero=barbero,
                inicio__date=fecha,
                estado__in=['Pendiente', 'Confirmada'],
                inicio__lt=fin_slot,
                fin__gt=inicio_datetime
            ).exists()
            
            if ocupado:
                raise forms.ValidationError(
                    f'La hora seleccionada ya no está disponible. Por favor selecciona otra hora.'
                )
            
            # Agregar los valores calculados al cleaned_data
            cleaned_data['inicio_calculado'] = inicio_datetime
            cleaned_data['fin_calculado'] = fin_datetime
        
        return cleaned_data