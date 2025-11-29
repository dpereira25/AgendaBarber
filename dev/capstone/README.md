# 💈 Crono Corte - Sistema de Gestión de Reservas para Barbería

Sistema web desarrollado en Django para gestionar reservas de servicios de barbería con integración de pagos mediante MercadoPago.

---

## 🚀 Características Principales

- ✅ **Sistema de Reservas Online** con selección de barbero, servicio y horario
- 💳 **Pagos Integrados** con MercadoPago (webhooks automáticos)
- 📊 **Panel Administrativo** con analytics y reportes
- 👥 **Gestión de Usuarios** (Clientes, Barberos, Administradores)
- 📱 **Diseño Responsive** (funciona en móviles y tablets)
- 🌙 **Modo Oscuro** persistente
- 🔒 **Seguridad Robusta** con protección de rutas y páginas de error personalizadas

---

## 🛠️ Tecnologías

- **Backend:** Django 4.2.6 (Python)
- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5.3.3
- **Base de Datos:** SQLite (desarrollo) / PostgreSQL (producción)
- **Pagos:** MercadoPago SDK 2.2.0
- **Gráficos:** Chart.js
- **Animaciones:** AOS (Animate On Scroll)

---

## 📋 Requisitos Previos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Cuenta de MercadoPago (para pagos)

---

## 🔧 Instalación

### 1. Clonar el repositorio
```bash
git clone <url-del-repositorio>
cd capstone
```

### 2. Crear entorno virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Crear archivo `.env` en la raíz del proyecto:
```env
DEBUG=True
SECRET_KEY=tu-secret-key-aqui

# MercadoPago
MERCADOPAGO_ACCESS_TOKEN=tu-token-de-mercadopago
MERCADOPAGO_PUBLIC_KEY=tu-public-key
MERCADOPAGO_SANDBOX=True
```

### 5. Ejecutar migraciones
```bash
python manage.py migrate
```

### 6. Crear superusuario
```bash
python manage.py createsuperuser
```

### 7. Recopilar archivos estáticos
```bash
python manage.py collectstatic --noinput
```

### 8. Iniciar servidor
```bash
python manage.py runserver
```

Acceder a: `http://localhost:8000`

---

## 👥 Roles de Usuario

### Cliente
- Crear y gestionar reservas
- Ver historial de reservas
- Cancelar reservas (con 2h de anticipación)
- Realizar pagos online

### Barbero
- Ver agenda personal
- Gestionar horarios de trabajo
- Ver estadísticas de ingresos
- Cancelar reservas

### Administrador
- Dashboard con métricas globales
- Gestionar barberos y servicios
- Exportar reportes
- Acceso completo al sistema

---

## 📁 Estructura del Proyecto

```
capstone/
├── agendabarber/          # App principal
│   ├── decorators.py      # Decoradores de seguridad
│   ├── models.py          # Modelos (Barbero, Servicio, Reserva, etc.)
│   ├── views.py           # Vistas del sistema
│   ├── services/          # Lógica de negocio (MercadoPago)
│   ├── templates/         # Templates HTML
│   └── static/            # CSS, JS, imágenes
├── panel/                 # App de analytics
│   ├── views.py           # Dashboard y reportes
│   └── analytics_service.py
├── capstone/              # Configuración Django
│   ├── settings.py
│   └── urls.py
├── logs/                  # Logs del sistema
├── media/                 # Archivos subidos (fotos)
├── staticfiles/           # Archivos estáticos compilados
├── .env                   # Variables de entorno (no incluir en git)
├── .env.example           # Ejemplo de variables
├── requirements.txt       # Dependencias Python
└── manage.py              # CLI de Django
```

---

## 🔒 Seguridad

### Protección Implementada:
- ✅ Páginas de error personalizadas (404, 500, 403)
- ✅ Decoradores de autenticación y autorización
- ✅ Protección CSRF
- ✅ Validación de permisos por rol
- ✅ Sistema de logging
- ✅ Configuraciones de seguridad para producción (HTTPS, cookies seguras, etc.)

### Decoradores Disponibles:
- `@login_required` - Requiere autenticación
- `@barbero_required` - Solo barberos
- `@admin_or_barbero_required` - Solo admin o barbero
- `@cliente_required` - Solo clientes

---

## 📊 Panel Administrativo

Acceder a: `http://localhost:8000/panel/`

**Métricas disponibles:**
- Total de ingresos
- Total de reservas
- Valor promedio por reserva
- Tasa de completación
- Servicios más populares
- Rendimiento por barbero
- Análisis de horas pico

**Filtros:**
- Últimos 7 días
- Últimos 30 días
- Este mes
- Mes pasado
- Este año

**Exportación:**
- Reportes en CSV

---

## 💳 Configuración de MercadoPago

### 1. Crear cuenta en MercadoPago
https://www.mercadopago.com.ar/developers

### 2. Obtener credenciales
- Access Token (TEST o PROD)
- Public Key

### 3. Configurar en .env
```env
MERCADOPAGO_ACCESS_TOKEN=TEST-xxxxx
MERCADOPAGO_PUBLIC_KEY=TEST-xxxxx
MERCADOPAGO_SANDBOX=True  # False para producción
```

### 4. Configurar Webhooks
URL del webhook: `https://tu-dominio.com/webhooks/mercadopago/`

---

## 🧪 Testing

### Probar páginas de error:
```
http://localhost:8000/pagina-inexistente  # 404
```

### Probar protección de rutas:
```
# Sin autenticarse:
http://localhost:8000/mis-reservas/       # Redirige a login
http://localhost:8000/agenda-barbero/     # Redirige a login
```

### Ver logs:
```bash
# Windows
type logs\django.log
type logs\errors.log

# Linux/Mac
cat logs/django.log
cat logs/errors.log
```

---

## 🚀 Despliegue a Producción

### Checklist:

1. **Configurar variables de entorno:**
```env
DEBUG=False
SECRET_KEY=clave-super-segura-aleatoria
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com
MERCADOPAGO_SANDBOX=False
```

2. **Configurar base de datos PostgreSQL:**
```env
DATABASE_URL=postgresql://user:password@localhost/dbname
```

3. **Configurar servidor web (Nginx/Apache)**

4. **Obtener certificado SSL (Let's Encrypt)**

5. **Ejecutar comandos:**
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

6. **Configurar Gunicorn:**
```bash
pip install gunicorn
gunicorn capstone.wsgi:application --bind 0.0.0.0:8000
```

---

## 📝 Comandos Útiles

```bash
# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Recopilar archivos estáticos
python manage.py collectstatic

# Iniciar servidor de desarrollo
python manage.py runserver

# Limpiar reservas temporales expiradas
python manage.py cleanup_expired_reservations

# Acceder a shell de Django
python manage.py shell
```

---

## 🐛 Solución de Problemas

### Error: "No module named 'PIL'"
```bash
pip install Pillow
```

### Error: "CSRF verification failed"
- Verificar que `CSRF_TRUSTED_ORIGINS` esté configurado en settings.py
- Incluir el dominio completo con protocolo (https://)

### Error 404 en archivos estáticos
```bash
python manage.py collectstatic --noinput
```

### Webhooks de MercadoPago no funcionan
- Verificar que la URL sea accesible públicamente (usar ngrok en desarrollo)
- Revisar logs en `logs/django.log`

---

## 📚 Documentación Adicional

Ver archivo `DOCUMENTACION.md` para información detallada sobre:
- Seguridad implementada
- Funcionalidades del sistema
- Guías de uso
- Troubleshooting

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crear rama de feature (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

---

## 📄 Licencia

Este proyecto es privado y confidencial.

---

## 👨‍💻 Autor

**Equipo Crono Corte**

---

## 📞 Soporte

Para reportar bugs o solicitar features, crear un issue en el repositorio.

---

**Última actualización:** Noviembre 2025  
**Versión:** 1.0  
**Estado:** ✅ Producción
