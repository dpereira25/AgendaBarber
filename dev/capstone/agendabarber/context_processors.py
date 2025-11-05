from .models import Barbero

def user_type_context(request):
    """
    🎯 PROCESADOR DE CONTEXTO PARA TIPOS DE USUARIO
    
    Esta función se ejecuta automáticamente en CADA página del sitio web
    y determina qué tipo de usuario está navegando para mostrar contenido personalizado.
    
    📋 Variables que agrega a TODOS los templates:
    - 'es_barbero': True si el usuario logueado es un barbero del sistema
    - 'es_cliente': True si el usuario logueado es un cliente normal
    - Ambas son False si el usuario no está logueado
    
    💡 Ejemplo de uso en templates:
    {% if es_barbero %}
        <h1>¡Hola barbero! Aquí está tu agenda del día</h1>
        <a href="/agenda-barbero/">Ver mi agenda</a>
    {% elif es_cliente %}
        <h1>¡Hola! ¿Quieres agendar una cita?</h1>
        <a href="/reservar/">Hacer reserva</a>
    {% else %}
        <h1>Bienvenido a AgendaBarber</h1>
        <a href="/auth/login/">Iniciar sesión</a>
    {% endif %}
    """
    
    # Inicializar variables por defecto (usuario no logueado)
    context = {
        'es_barbero': False,
        'es_cliente': False,
    }
    
    # Solo procesar si hay un usuario autenticado
    if request.user.is_authenticated:
        try:
            # Intentar encontrar al usuario en la tabla de Barberos
            Barbero.objects.get(usuario=request.user)
            # Si lo encuentra, es un barbero
            context['es_barbero'] = True
            context['es_cliente'] = False
        except Barbero.DoesNotExist:
            # Si no lo encuentra, es un cliente normal
            context['es_barbero'] = False
            context['es_cliente'] = True
    
    return context