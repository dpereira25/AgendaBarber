from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta, time, date
from .models import Reserva, Servicio, Barbero


class CustomUserCreationForm(UserCreationForm):
    """
    Formulario personalizado de registro que incluye nombre, apellido y email
    """
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu nombre'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu apellido'})
    )
    email = forms.EmailField(
        max_length=254,
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'tu@email.com'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.email = self.cleaned_data.get('email', '')
        if commit:
            user.save()
        return user

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
    
    # Email no necesario - se usa el del usuario logueado
    
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
            raise forms.ValidationError('No puedes reservar en una fecha pasada. Selecciona una fecha válida para proceder al pago.')
        return fecha
    
    def clean_hora(self):
        """
        Validar que la hora tenga el formato correcto
        """
        hora_str = self.cleaned_data.get('hora')
        
        if not hora_str:
            raise forms.ValidationError(
                'Debes seleccionar una hora del menú desplegable para proceder al pago. '
                'Asegúrate de haber seleccionado fecha y barbero primero para ver las horas disponibles.'
            )
        
        try:
            # Validar formato de hora
            datetime.strptime(hora_str, '%H:%M')
        except ValueError:
            raise forms.ValidationError('Formato de hora inválido. Selecciona una hora válida del menú desplegable.')
        
        return hora_str
    
    # Email validation removed - using logged user's email
    
    def clean(self):
        """
        Validación general del formulario con validaciones mejoradas para el flujo de pago
        """
        cleaned_data = super().clean()
        fecha = cleaned_data.get('fecha')
        hora = cleaned_data.get('hora')
        barbero = cleaned_data.get('barbero')
        servicio = cleaned_data.get('servicio')
        # email removed - using logged user's email
        
        if fecha and hora and barbero and servicio:
            # Convertir hora string a time object
            try:
                hora_obj = datetime.strptime(hora, '%H:%M').time()
            except ValueError:
                raise forms.ValidationError('Formato de hora inválido. Selecciona una hora válida.')
            
            # Validar que la fecha no sea muy lejana (máximo 30 días)
            max_date = date.today() + timedelta(days=30)
            if fecha > max_date:
                raise forms.ValidationError(
                    f'No se pueden hacer reservas con más de 30 días de anticipación. '
                    f'La fecha máxima es {max_date.strftime("%d/%m/%Y")}.'
                )
            
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
                    raise forms.ValidationError('No trabajamos los domingos. Selecciona otro día.')
                elif 1 <= dia_semana <= 5:  # Lunes a viernes
                    hora_inicio = time(18, 0)
                    hora_fin = time(21, 0)
                elif dia_semana == 6:  # Sábado
                    hora_inicio = time(9, 0)
                    hora_fin = time(18, 0)
            
            # Verificar que la hora esté dentro del rango de trabajo
            if not (hora_inicio <= hora_obj < hora_fin):
                raise forms.ValidationError(
                    f'La hora seleccionada está fuera del horario de trabajo. '
                    f'Horario disponible: {hora_inicio.strftime("%H:%M")} - {hora_fin.strftime("%H:%M")}.'
                )
            
            # Crear datetime para la reserva
            inicio_datetime = timezone.make_aware(
                datetime.combine(fecha, hora_obj)
            )
            
            # Validar que la reserva no sea en el pasado (con margen de 30 minutos para pruebas)
            min_datetime = timezone.now() + timedelta(minutes=30)
            if inicio_datetime < min_datetime:
                current_time = timezone.now()
                raise forms.ValidationError(
                    'No se pueden hacer reservas con menos de 30 minutos de anticipación. '
                    f'Hora actual: {current_time.strftime("%d/%m/%Y %H:%M")}. '
                    f'Hora mínima para reservar: {min_datetime.strftime("%d/%m/%Y %H:%M")}.'
                )
            
            # Calcular fin basado en la duración del servicio
            fin_datetime = inicio_datetime + timedelta(minutes=servicio.duracion_minutos)
            
            # Verificar que el servicio termine dentro del horario de trabajo
            hora_fin_servicio = fin_datetime.time()
            if hora_fin_servicio > hora_fin:
                raise forms.ValidationError(
                    f'El servicio seleccionado ({servicio.duracion_minutos} minutos) no puede completarse '
                    f'dentro del horario de trabajo. Selecciona una hora más temprana.'
                )
            
            # Verificar disponibilidad con manejo de concurrencia mejorado
            from .services.temporary_reservation_service import TemporaryReservationService
            from django.db import transaction
            
            # Usar transacción para verificar disponibilidad de forma atómica
            try:
                with transaction.atomic():
                    # Limpiar reservas temporales expiradas antes de verificar disponibilidad
                    TemporaryReservationService.cleanup_expired_reservations()
                    
                    # Verificar disponibilidad
                    if not TemporaryReservationService.is_time_slot_available(barbero, inicio_datetime, fin_datetime):
                        # Obtener información específica sobre el conflicto
                        conflict_info = self._get_availability_conflict_info(barbero, inicio_datetime, fin_datetime)
                        raise forms.ValidationError(conflict_info['message'])
            except Exception as e:
                if isinstance(e, forms.ValidationError):
                    raise
                else:
                    # Error inesperado al verificar disponibilidad
                    raise forms.ValidationError(
                        'Error al verificar la disponibilidad del horario. '
                        'Por favor inténtalo de nuevo o selecciona otra hora.'
                    )
            
            # Validar que el barbero esté activo/disponible
            if not self._is_barbero_available(barbero, fecha):
                raise forms.ValidationError(
                    f'El barbero {barbero.nombre} no está disponible en la fecha seleccionada.'
                )
            
            # Agregar los valores calculados al cleaned_data
            cleaned_data['inicio_calculado'] = inicio_datetime
            cleaned_data['fin_calculado'] = fin_datetime
        
        return cleaned_data
    
    def _get_availability_conflict_info(self, barbero, inicio, fin):
        """
        Obtiene información específica sobre por qué un horario no está disponible
        """
        from .models import Reserva, TemporaryReservation
        
        # Verificar reservas confirmadas
        existing_reserva = Reserva.objects.filter(
            barbero=barbero,
            inicio__lt=fin,
            fin__gt=inicio,
            estado__in=['Pendiente', 'Confirmada']
        ).first()
        
        if existing_reserva:
            return {
                'type': 'confirmed_reservation',
                'message': (
                    f'Ya existe una reserva confirmada de {existing_reserva.inicio.strftime("%H:%M")} '
                    f'a {existing_reserva.fin.strftime("%H:%M")}. Por favor selecciona otra hora.'
                )
            }
        
        # Verificar reservas temporales
        temp_reserva = TemporaryReservation.objects.active().filter(
            barbero=barbero,
            inicio__lt=fin,
            fin__gt=inicio
        ).first()
        
        if temp_reserva:
            expires_in = temp_reserva.time_remaining
            minutes_remaining = int(expires_in.total_seconds() / 60)
            return {
                'type': 'temporary_reservation',
                'message': (
                    f'Este horario está temporalmente bloqueado por otro cliente '
                    f'(se libera en {minutes_remaining} minutos). '
                    f'Por favor selecciona otra hora o inténtalo más tarde.'
                )
            }
        
        # Caso genérico
        return {
            'type': 'unknown',
            'message': (
                'La hora seleccionada ya no está disponible. '
                'Por favor selecciona otra hora.'
            )
        }
    
    def _is_barbero_available(self, barbero, fecha):
        """
        Verifica si el barbero está disponible en la fecha dada
        (puede expandirse para incluir vacaciones, días libres, etc.)
        """
        # Por ahora, verificar que tenga horario de trabajo para ese día
        from .models import HorarioTrabajo
        dia_semana = fecha.isoweekday()
        
        # Domingo siempre no disponible
        if dia_semana == 7:
            return False
        
        # Verificar si tiene horario específico configurado
        try:
            HorarioTrabajo.objects.get(barbero=barbero, dia_semana=dia_semana)
            return True
        except HorarioTrabajo.DoesNotExist:
            # Usar horarios por defecto (lunes a sábado)
            return dia_semana in [1, 2, 3, 4, 5, 6]



class BarberoForm(forms.ModelForm):
    """Formulario para crear y editar barberos"""
    
    # Campos para crear usuario (siempre requeridos al crear)
    nuevo_username = forms.CharField(
        max_length=150,
        required=True,
        label='Nombre de usuario',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: barbero_juan'
        })
    )
    
    nuevo_email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'barbero@cronocorte.com'
        })
    )
    
    nuevo_password = forms.CharField(
        required=True,
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña segura'
        })
    )
    
    nuevo_password_confirm = forms.CharField(
        required=True,
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite la contraseña'
        })
    )
    
    class Meta:
        model = Barbero
        fields = ['nombre', 'experiencia', 'foto']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo del barbero'
            }),
            'experiencia': forms.Select(
                choices=[(i, f'{i} año{"s" if i != 1 else ""}') for i in range(0, 31)],
                attrs={
                    'class': 'form-select',
                    'size': '1',
                    'style': 'height: auto;'
                }
            ),
            'foto': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'nombre': 'Nombre Completo',
            'experiencia': 'Años de Experiencia',
            'foto': 'Foto de Perfil',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si estamos editando, ocultar los campos de usuario
        if self.instance.pk:
            # Eliminar los campos de usuario del formulario al editar
            del self.fields['nuevo_username']
            del self.fields['nuevo_email']
            del self.fields['nuevo_password']
            del self.fields['nuevo_password_confirm']
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Solo validar si estamos creando (los campos no existen al editar)
        if not self.instance.pk:
            nuevo_username = cleaned_data.get('nuevo_username')
            nuevo_email = cleaned_data.get('nuevo_email')
            nuevo_password = cleaned_data.get('nuevo_password')
            nuevo_password_confirm = cleaned_data.get('nuevo_password_confirm')
            
            if nuevo_username and User.objects.filter(username=nuevo_username).exists():
                self.add_error('nuevo_username', 'Este nombre de usuario ya existe')
            
            if nuevo_email and User.objects.filter(email=nuevo_email).exists():
                self.add_error('nuevo_email', 'Este email ya está registrado')
            
            if nuevo_password and len(nuevo_password) < 8:
                self.add_error('nuevo_password', 'La contraseña debe tener al menos 8 caracteres')
            
            if nuevo_password != nuevo_password_confirm:
                self.add_error('nuevo_password_confirm', 'Las contraseñas no coinciden')
        
        return cleaned_data
    
    def save(self, commit=True):
        barbero = super().save(commit=False)
        
        # Solo crear usuario si estamos creando un barbero nuevo
        if not self.instance.pk:
            nuevo_username = self.cleaned_data.get('nuevo_username')
            nuevo_email = self.cleaned_data.get('nuevo_email')
            nuevo_password = self.cleaned_data.get('nuevo_password')
            
            if nuevo_username and nuevo_email and nuevo_password:
                nuevo_usuario = User.objects.create_user(
                    username=nuevo_username,
                    email=nuevo_email,
                    password=nuevo_password,
                    first_name=barbero.nombre.split()[0] if barbero.nombre else '',
                    last_name=' '.join(barbero.nombre.split()[1:]) if len(barbero.nombre.split()) > 1 else '',
                    is_staff=False  # Los barberos NO son staff, solo tienen acceso a su agenda
                )
                barbero.usuario = nuevo_usuario
        else:
            # Al editar, actualizar el nombre del usuario si cambió el nombre del barbero
            if barbero.usuario:
                barbero.usuario.first_name = barbero.nombre.split()[0] if barbero.nombre else ''
                barbero.usuario.last_name = ' '.join(barbero.nombre.split()[1:]) if len(barbero.nombre.split()) > 1 else ''
                barbero.usuario.save()
        
        if commit:
            barbero.save()
        
        return barbero
