from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, time, timedelta
from .models import Barbero, Servicio, Reserva

class ReservaForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'min': timezone.now().date().isoformat()
        }),
        label="Fecha"
    )
    hora = forms.ChoiceField(
        choices=[],  # Se llenarán dinámicamente
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Hora"
    )

    class Meta:
        model = Reserva
        fields = ['barbero', 'servicio', 'fecha', 'hora']
        widgets = {
            'barbero': forms.Select(attrs={'class': 'form-select'}),
            'servicio': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Agregar clases CSS a los campos
        self.fields['fecha'].widget.attrs.update({'class': 'form-control'})
        
        # Personalizar las opciones de servicio para incluir precios
        servicios = Servicio.objects.all()
        servicio_choices = [('', 'Selecciona un servicio')]
        for servicio in servicios:
            servicio_choices.append((servicio.id, f"{servicio.nombre} - ${servicio.precio:,}"))
        self.fields['servicio'].choices = servicio_choices
        
        # Inicializar horas disponibles (se actualizarán con JavaScript)
        # Para tests, incluir algunas horas básicas
        horas_basicas = [('', 'Selecciona fecha y barbero primero')]
        for hora in range(9, 22):  # 9:00 a 21:00
            hora_str = f"{hora:02d}:00"
            horas_basicas.append((hora_str, hora_str))
        self.fields['hora'].choices = horas_basicas

    def clean_fecha(self):
        """Solo validar domingos (fechas pasadas ya están bloqueadas por el widget)"""
        fecha = self.cleaned_data.get('fecha')
        if fecha and fecha.isoweekday() == 7:
            raise ValidationError('La barbería está cerrada los domingos.')
        return fecha

    def clean_hora(self):
        """Convertir la hora de string a time object"""
        hora_str = self.cleaned_data.get('hora')
        if hora_str:
            try:
                # Convertir "18:00" a time object
                hora = datetime.strptime(hora_str, '%H:%M').time()
                return hora
            except ValueError:
                raise ValidationError('Formato de hora inválido.')
        return hora_str

    def clean(self):
        """Validar horarios y disponibilidad"""
        cleaned_data = super().clean()
        fecha = cleaned_data.get('fecha')
        hora = cleaned_data.get('hora')
        barbero = cleaned_data.get('barbero')
        servicio = cleaned_data.get('servicio')
        
        if not all([fecha, hora, barbero, servicio]):
            return cleaned_data
        
        # Crear datetime de la reserva
        inicio_reserva = timezone.make_aware(datetime.combine(fecha, hora))
        duracion = timedelta(minutes=servicio.duracion_minutos)
        fin_reserva = inicio_reserva + duracion
        
        # Validar horarios según el día
        dia_semana = fecha.isoweekday()
        if 1 <= dia_semana <= 5:  # Lunes a viernes
            if hora < time(18, 0) or hora >= time(21, 0):
                raise ValidationError('Horario de lunes a viernes: 18:00 - 21:00')
        elif dia_semana == 6:  # Sábado
            if hora < time(9, 0) or hora >= time(18, 0):
                raise ValidationError('Horario de sábados: 09:00 - 18:00')
        
        # Verificar solapamientos
        solapamientos = Reserva.objects.filter(
            barbero=barbero,
            inicio__date=fecha,
            estado__in=['Pendiente', 'Confirmada'],
            inicio__lt=fin_reserva,
            fin__gt=inicio_reserva
        ).exists()
        
        if solapamientos:
            raise ValidationError('Esta franja horaria ya está ocupada.')
        
        # Guardar valores calculados
        cleaned_data['inicio_calculado'] = inicio_reserva
        cleaned_data['fin_calculado'] = fin_reserva
        
        return cleaned_data
