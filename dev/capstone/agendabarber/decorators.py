"""
Decoradores personalizados para protección de vistas
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from functools import wraps
from .models import Barbero


def barbero_required(view_func):
    """
    Decorador para vistas que requieren que el usuario sea un barbero.
    Redirige a inicio si no tiene permisos.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesión para acceder a esta página.')
            return redirect('login')
        
        try:
            Barbero.objects.get(usuario=request.user)
        except Barbero.DoesNotExist:
            messages.error(request, 'No tienes permisos de barbero. Contacta al administrador.')
            return redirect('inicio')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def admin_or_barbero_required(view_func):
    """
    Decorador para vistas que requieren ser administrador o barbero.
    Usado principalmente en el panel administrativo.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesión para acceder al panel administrativo.')
            return redirect('login')
        
        # Verificar si es superuser o barbero
        is_admin = request.user.is_superuser
        is_barbero = Barbero.objects.filter(usuario=request.user).exists()
        
        if not (is_admin or is_barbero):
            messages.error(request, 'No tienes permisos para acceder al panel administrativo.')
            return redirect('inicio')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def cliente_required(view_func):
    """
    Decorador para vistas que requieren que el usuario sea un cliente
    (usuario autenticado que NO es barbero).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesión para acceder a esta página.')
            return redirect('login')
        
        # Verificar que NO sea barbero (es cliente)
        if Barbero.objects.filter(usuario=request.user).exists():
            messages.info(request, 'Esta sección es solo para clientes.')
            return redirect('agenda_barbero')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def ajax_login_required(view_func):
    """
    Decorador para vistas AJAX que requieren autenticación.
    Retorna JSON en lugar de redirigir.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({
                'success': False,
                'message': 'Debes iniciar sesión para realizar esta acción.',
                'redirect': '/auth/login/'
            }, status=401)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
