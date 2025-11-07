#!/usr/bin/env python
"""
Script personalizado para ejecutar el servidor Django con Pillow forzado
"""
import os
import sys

# Forzar importación de Pillow antes de Django
try:
    from PIL import Image
    print(f"✅ Pillow {Image.__version__} cargado correctamente")
except ImportError as e:
    print(f"❌ Error cargando Pillow: {e}")
    sys.exit(1)

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capstone.settings')

# Importar Django después de Pillow
import django
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    # Ejecutar el servidor
    execute_from_command_line(['manage.py', 'runserver'])