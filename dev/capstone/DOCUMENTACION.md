# 📚 Documentación del Proyecto - Crono Corte

## 📋 Índice
1. [Seguridad Implementada](#seguridad-implementada)
2. [Cambios Recientes](#cambios-recientes)
3. [Funcionalidades del Sistema](#funcionalidades-del-sistema)

---

## 🔒 Seguridad Implementada

### Páginas de Error Personalizadas
- ✅ `404.html` - Página no encontrada
- ✅ `500.html` - Error del servidor
- ✅ `403.html` - Acceso denegado

**Características:**
- Diseño consistente con el tema del sitio (dorado/negro)
- Botones de navegación para volver al inicio
- Mensajes claros y amigables
- Responsive (funciona en móviles)

### Decoradores de Seguridad

**Archivo:** `agendabarber/decorators.py`

**Decoradores disponibles:**

1. **`@barbero_required`**
   - Verifica que el usuario sea un barbero
   - Redirige a login si no está autenticado
   - Redirige a inicio si no tiene permisos

2. **`@admin_or_barbero_required`**
   - Verifica que el usuario sea admin o barbero
   - Usado en el panel administrativo

3. **`@cliente_required`**
   - Verifica que el usuario sea cliente (no barbero)
   - Útil para vistas exclusivas de clientes

4. **`@ajax_login_required`**
   - Para peticiones AJAX que requieren autenticación
   - Retorna JSON en lugar de redirigir

### Vistas Protegidas

| Vista | Decorador | Descripción |
|-------|-----------|-------------|
| `agenda_barbero()` | `@barbero_required` | Solo barberos |
| `mis_reservas_cliente()` | `@login_required` | Solo usuarios autenticados |
| `crearReserva()` | `@login_required` | Solo usuarios autenticados |
| `cancelar_reserva()` | `@login_required` + `@require_POST` | Solo dueño de reserva |
| `dashboard()` | `@admin_or_barbero_required` | Solo admin/barbero |

### Sistema de Logging

**Configuración en `settings.py`:**

- **Console Handler:** Muestra logs en consola (desarrollo)
- **File Handler:** Guarda todos los logs en `logs/django.log`
- **Error File Handler:** Guarda solo errores en `logs/errors.log`

**Niveles:**
- DEBUG mode: Nivel DEBUG (muestra todo)
- Production mode: Nivel INFO (solo importante)

### Configuración de Seguridad para Producción

Cuando `DEBUG=False`, se activan automáticamente:
- `SECURE_SSL_REDIRECT = True` - Forzar HTTPS
- `SESSION_COOKIE_SECURE = True` - Cookies solo por HTTPS
- `CSRF_COOKIE_SECURE = True` - CSRF solo por HTTPS
- `SECURE_BROWSER_XSS_FILTER = True` - Protección XSS
- `SECURE_CONTENT_TYPE_NOSNIFF = True` - Prevenir MIME sniffing
- `X_FRAME_OPTIONS = 'DENY'` - Prevenir clickjacking
- `SECURE_HSTS_SECONDS = 31536000` - HSTS por 1 año

---

## 📝 Cambios Recientes

### Última Actualización: Noviembre 2025

#### Archivos Creados:
- `agendabarber/decorators.py` - Decoradores de seguridad
- `agendabarber/templates/404.html` - Página de error 404
- `agendabarber/templates/500.html` - Página de error 500
- `agendabarber/templates/403.html` - Página de error 403
- `logs/` - Directorio para logs del sistema

#### Archivos Modificados:
- `agendabarber/views.py` - Actualizado con decoradores
- `panel/views.py` - Actualizado con decoradores centralizados
- `capstone/settings.py` - Agregado logging y seguridad
- `.gitignore` - Agregado logs/

#### Archivos Eliminados:
- `test_seguridad.py` - Script temporal de prueba
- `run_server.py` - Redundante (usar manage.py)
- `confirmacionReserva.html` - Template sin uso
- Archivos de documentación temporal duplicados

---

## 🎯 Funcionalidades del Sistema

### 1. Gestión de Reservas

**Cancelación de Reservas:**
- ✅ Clientes pueden cancelar sus propias reservas
- ✅ Barberos pueden cancelar reservas asignadas a ellos
- ⏰ Restricción: No se puede cancelar con menos de 2 horas de anticipación
- ❌ No se pueden cancelar reservas ya Canceladas o Completadas

**Proceso de Reserva:**
1. Cliente selecciona servicio y barbero
2. Sistema muestra horarios disponibles
3. Cliente selecciona horario
4. Sistema crea reserva temporal (15 min de bloqueo)
5. Cliente paga con MercadoPago
6. Sistema recibe webhook de confirmación
7. Reserva temporal se convierte en definitiva

### 2. Sistema de Pagos

**Integración MercadoPago:**
- Checkout con preferencia de pago
- Webhooks para confirmación automática
- Estados: pending, approved, rejected
- Auditoría completa de transacciones
- Timeout de 15 minutos para completar pago

### 3. Panel Administrativo

**Métricas Disponibles:**
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
- Reportes en formato CSV
- Datos completos de reservas y métricas

### 4. Roles de Usuario

**Cliente:**
- Crear reservas
- Ver historial de reservas
- Cancelar reservas futuras
- Ver catálogo de servicios
- Actualizar perfil

**Barbero:**
- Ver agenda personal
- Filtrar reservas (hoy, semana, pendientes)
- Ver estadísticas de ingresos
- Cancelar reservas
- Gestionar horarios de trabajo

**Administrador:**
- Dashboard con métricas globales
- Gestionar barberos y servicios
- Ver reportes y analytics
- Exportar datos
- Acceso completo al sistema

---

## 🧪 Cómo Probar

### Probar Páginas de Error:
```
# 404 - Página no encontrada
http://localhost:8000/pagina-inexistente

# 403 - Acceso denegado (sin autenticarse)
http://localhost:8000/agenda-barbero/
```

### Probar Protección de Rutas:
```bash
# Sin autenticarse, intentar acceder a:
http://localhost:8000/mis-reservas/
http://localhost:8000/agenda-barbero/
http://localhost:8000/reservar/

# Resultado esperado: Redirige a login
```

### Verificar Logs:
```bash
# Windows
type logs\django.log
type logs\errors.log

# Linux/Mac
cat logs/django.log
cat logs/errors.log
```

---

## ⚠️ Antes de Producción

### Checklist:

- [ ] Cambiar `DEBUG = False` en settings.py o .env
- [ ] Configurar `ALLOWED_HOSTS` con tu dominio
- [ ] Configurar certificado SSL (HTTPS)
- [ ] Configurar servidor web (Nginx/Apache)
- [ ] Configurar base de datos PostgreSQL
- [ ] Ejecutar `python manage.py collectstatic`
- [ ] Configurar variables de entorno (.env)
- [ ] Configurar backup automático de BD
- [ ] Probar todas las funcionalidades

### Variables de Entorno Requeridas:

```env
DEBUG=False
SECRET_KEY=tu-secret-key-super-segura
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com

# MercadoPago
MERCADOPAGO_ACCESS_TOKEN=tu-token
MERCADOPAGO_PUBLIC_KEY=tu-public-key
MERCADOPAGO_SANDBOX=False

# Base de Datos (Producción)
DATABASE_URL=postgresql://user:password@localhost/dbname
```

---

## 📞 Soporte

### Logs de Errores:
```bash
# Ver últimos errores
tail -f logs/errors.log

# Ver todos los logs
tail -f logs/django.log
```

### Problemas Comunes:

**Error 404 en archivos estáticos:**
```bash
python manage.py collectstatic --noinput
```

**Error de permisos:**
- Verificar que el usuario tenga rol correcto (cliente/barbero)
- Revisar decoradores en las vistas

**Error de pago:**
- Verificar credenciales de MercadoPago en .env
- Revisar logs de webhooks en `logs/django.log`

---

## 📊 Estructura del Proyecto

```
capstone/
├── agendabarber/          # App principal
│   ├── decorators.py      # Decoradores de seguridad
│   ├── models.py          # Modelos de datos
│   ├── views.py           # Vistas del sistema
│   ├── forms.py           # Formularios
│   ├── services/          # Servicios de negocio
│   ├── templates/         # Templates HTML
│   └── static/            # Archivos estáticos
├── panel/                 # App de analytics
│   ├── views.py           # Dashboard y reportes
│   └── analytics_service.py
├── capstone/              # Configuración
│   ├── settings.py        # Configuración Django
│   └── urls.py            # Rutas principales
├── logs/                  # Logs del sistema
├── media/                 # Archivos subidos
├── staticfiles/           # Archivos estáticos compilados
└── manage.py              # CLI de Django
```

---

## 🔗 Enlaces Útiles

- **Django Documentation:** https://docs.djangoproject.com/
- **MercadoPago API:** https://www.mercadopago.com.ar/developers
- **Bootstrap 5:** https://getbootstrap.com/docs/5.3/
- **Chart.js:** https://www.chartjs.org/

---

**Última actualización:** Noviembre 2025  
**Versión:** 1.0  
**Estado:** ✅ Producción
