# AgendaBarber
Proyecto de capstone AgendaBarber - Sistema de gestión para barberías.

## Configuración del Entorno de Desarrollo

### Requisitos
- Python 3.14.0 (ya instalado)
- Git (para control de versiones)

### Instalación

1. **Clonar el repositorio** (si aún no lo has hecho):
   ```bash
   git clone <url-del-repositorio>
   cd AgendaBarber
   ```

2. **Activar el entorno virtual**:
   - **Opción 1**: Ejecutar el script automático
     ```bash
     activate_env.bat
     ```
   
   - **Opción 2**: Activar manualmente
     ```bash
     venv\Scripts\activate
     ```

3. **Verificar instalación**:
   ```bash
   pip list
   python dev/capstone/manage.py check
   ```

### Ejecutar el Proyecto

1. **Activar el entorno virtual** (si no está activado):
   ```bash
   venv\Scripts\activate
   ```

2. **Navegar al directorio del proyecto Django**:
   ```bash
   cd dev\capstone
   ```

3. **Ejecutar migraciones** (primera vez):
   ```bash
   python manage.py migrate
   ```

4. **Iniciar el servidor de desarrollo**:
   ```bash
   python manage.py runserver
   ```

5. **Abrir en el navegador**: http://127.0.0.1:8000/

### Estructura del Proyecto
```
AgendaBarber/
├── venv/                 # Entorno virtual
├── dev/
│   └── capstone/        # Proyecto Django principal
│       ├── manage.py    # Script de gestión de Django
│       ├── capstone/    # Configuración del proyecto
│       └── panel/       # Aplicación principal
├── FASE 1/              # Documentación Fase 1
├── FASE 2/              # Documentación Fase 2
└── README.md           # Este archivo
```

### Dependencias Principales
- Django 4.2.6
- django-leaflet 0.29.0 (mapas)
- folium 0.15.0 (visualización de mapas)
- transbank-sdk 5.0.0 (pagos)
- python-dotenv 1.1.1 (variables de entorno)
- Pillow (procesamiento de imágenes)
- numpy (cálculos numéricos)

### Comandos Útiles

- **Crear superusuario**:
  ```bash
  python manage.py createsuperuser
  ```

- **Hacer migraciones**:
  ```bash
  python manage.py makemigrations
  python manage.py migrate
  ```

- **Recopilar archivos estáticos**:
  ```bash
  python manage.py collectstatic
  ```

### Notas
- El entorno virtual está configurado y todas las dependencias están instaladas
- El archivo `.gitignore` está configurado para excluir el entorno virtual
- Usa `deactivate` para salir del entorno virtual
