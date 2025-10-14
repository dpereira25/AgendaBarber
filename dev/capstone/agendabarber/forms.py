from django import forms
from .models import Barbero, Servicio, Reserva

class ReservaForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Fecha"
    )
    hora = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time'}),
        label="Hora"
    )

    class Meta:
        model = Reserva
        fields = ['barbero', 'servicio', 'fecha', 'hora']
