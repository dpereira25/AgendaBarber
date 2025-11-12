from django.contrib import admin
from django.utils.html import format_html
from .models import Barbero, Servicio, Reserva

@admin.register(Barbero)
class BarberoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario_info', 'experiencia', 'es_usuario_barbero', 'foto_preview')
    list_filter = ('experiencia',)
    search_fields = ('nombre', 'usuario__username', 'usuario__first_name', 'usuario__last_name')
    ordering = ('nombre',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'experiencia', 'foto')
        }),
        ('Usuario Asociado', {
            'fields': ('usuario',),
            'description': 'Selecciona el usuario que tendrá acceso como barbero. '
                          'Solo usuarios sin barbero asignado aparecerán en la lista.'
        }),
    )
    
    def usuario_info(self, obj):
        if obj.usuario:
            return format_html(
                '<span style="color: green;">✓ {}</span>',
                obj.usuario.username
            )
        return format_html('<span style="color: red;">✗ Sin usuario</span>')
    usuario_info.short_description = 'Usuario Asignado'
    
    def foto_preview(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%;" />',
                obj.foto.url
            )
        return "Sin foto"
    foto_preview.short_description = 'Foto'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('usuario')

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_formateado', 'duracion_minutos', 'imagen_preview')
    list_filter = ('precio', 'duracion_minutos')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)
    
    def precio_formateado(self, obj):
        return f"${obj.precio:,}"
    precio_formateado.short_description = 'Precio'
    
    def imagen_preview(self, obj):
        if obj.imagen:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover;" />',
                obj.imagen.url
            )
        return "Sin imagen"
    imagen_preview.short_description = 'Imagen'

@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ('cliente_info', 'barbero', 'servicio', 'fecha_hora', 'estado_badge', 'pagado_badge')
    list_filter = ('estado', 'pagado', 'barbero', 'servicio')
    search_fields = ('cliente__username', 'cliente__first_name', 'cliente__last_name', 'barbero__nombre')
    date_hierarchy = 'inicio'
    ordering = ('-inicio',)
    
    fieldsets = (
        ('Información de la Reserva', {
            'fields': ('cliente', 'barbero', 'servicio')
        }),
        ('Fecha y Hora', {
            'fields': ('inicio', 'fin'),
            'description': 'La hora de fin se calcula automáticamente basada en la duración del servicio.'
        }),
        ('Estado y Pago', {
            'fields': ('estado', 'pagado')
        }),
    )
    
    readonly_fields = ('fin',)  # Fin se calcula automáticamente
    
    def cliente_info(self, obj):
        return f"{obj.cliente.get_full_name() or obj.cliente.username}"
    cliente_info.short_description = 'Cliente'
    
    def fecha_hora(self, obj):
        return format_html(
            '<strong>{}</strong><br/><small>{} - {}</small>',
            obj.inicio.strftime('%d/%m/%Y'),
            obj.inicio.strftime('%H:%M'),
            obj.fin.strftime('%H:%M') if obj.fin else 'N/A'
        )
    fecha_hora.short_description = 'Fecha y Hora'
    
    def estado_badge(self, obj):
        colors = {
            'Pendiente': 'orange',
            'Confirmada': 'green',
            'Cancelada': 'red',
            'Completada': 'blue'
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.estado
        )
    estado_badge.short_description = 'Estado'
    
    def pagado_badge(self, obj):
        if obj.pagado:
            return format_html('<span style="color: green;">✓ Pagado</span>')
        return format_html('<span style="color: red;">✗ Pendiente</span>')
    pagado_badge.short_description = 'Pago'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cliente', 'barbero', 'servicio')

# Personalizar el título del admin
admin.site.site_header = "Administración - Crono Corte"
admin.site.site_title = "Crono Corte Admin"
admin.site.index_title = "Panel de Administración"
