from .models import Barbero

def user_type_context(request):
    """Context processor para determinar el tipo de usuario"""
    context = {
        'es_barbero': False,
        'es_cliente': False,
    }
    
    if request.user.is_authenticated:
        # Verificar si es barbero
        try:
            Barbero.objects.get(usuario=request.user)
            context['es_barbero'] = True
        except Barbero.DoesNotExist:
            context['es_cliente'] = True
    
    return context