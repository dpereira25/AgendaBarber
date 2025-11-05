// ✅ VERSIÓN 2.0 - URLs corregidas (sin /api/)
console.log('📦 JavaScript de reservas v2.0 cargado - URLs sin /api/');

// Función principal que se ejecuta cuando el DOM está listo
function inicializarReservas() {
    console.log('🚀 Inicializando sistema de reservas v2.0...');
    
    try {
        // Obtener elementos del DOM con verificación
        const elementos = {
            fechaInput: document.getElementById('id_fecha'),
            barberoSelect: document.getElementById('id_barbero'),
            servicioSelect: document.getElementById('id_servicio'),
            horaSelect: document.getElementById('id_hora_select'),
            horaHidden: document.getElementById('id_hora_hidden'),
            servicioInfo: document.getElementById('servicio-info'),
            horarioSugerencia: document.getElementById('horario-sugerencia')
        };
        
        // Verificar elementos críticos
        const elementosFaltantes = [];
        Object.keys(elementos).forEach(key => {
            if (!elementos[key]) {
                elementosFaltantes.push(key);
            }
        });
        
        if (elementosFaltantes.length > 0) {
            console.error('❌ Elementos faltantes:', elementosFaltantes);
            return false;
        }
        
        console.log('✅ Todos los elementos encontrados correctamente');
        
        // Extraer elementos para uso local
        const { fechaInput, barberoSelect, servicioSelect, horaSelect, horaHidden, servicioInfo, horarioSugerencia } = elementos;

    // Función para cargar horas disponibles
    function cargarHorasDisponibles() {
        const fecha = fechaInput.value;
        const barberoId = barberoSelect.value;

        if (!fecha || !barberoId) {
            horaSelect.innerHTML = '<option value="">Selecciona fecha y barbero primero</option>';
            horaSelect.disabled = true;
            return;
        }

        // Mostrar loading
        horaSelect.innerHTML = '<option value="">Cargando horas disponibles...</option>';
        horaSelect.disabled = true;

        // Hacer petición AJAX
        console.log('🔍 Cargando horas para:', { fecha, barberoId });
        fetch(`/horas-disponibles/?fecha=${fecha}&barbero=${barberoId}`)
            .then(response => response.json())
            .then(data => {
                horaSelect.innerHTML = '<option value="">Selecciona una hora</option>';
                
                if (data.horas && data.horas.length > 0) {
                    data.horas.forEach(hora => {
                        const option = document.createElement('option');
                        option.value = hora.value;
                        option.textContent = hora.text;
                        horaSelect.appendChild(option);
                    });
                    horaSelect.disabled = false;
                    horarioSugerencia.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i>Horas disponibles cargadas';
                } else {
                    horaSelect.innerHTML = '<option value="">No hay horas disponibles</option>';
                    horarioSugerencia.innerHTML = '<i class="fas fa-exclamation-triangle text-warning me-1"></i>No hay horarios disponibles para esta fecha';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                horaSelect.innerHTML = '<option value="">Error al cargar horas</option>';
                horarioSugerencia.innerHTML = '<i class="fas fa-exclamation-circle text-danger me-1"></i>Error al cargar horarios disponibles';
            });
    }

    // Función para mostrar información del servicio
    function mostrarInfoServicio() {
        const servicioId = servicioSelect.value;

        if (!servicioId) {
            servicioInfo.innerHTML = '';
            return;
        }

        // Hacer petición AJAX para obtener info del servicio
        console.log('💰 Cargando info del servicio:', servicioId);
        fetch(`/info-servicio/?servicio_id=${servicioId}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    servicioInfo.innerHTML = '<i class="fas fa-exclamation-circle text-danger me-1"></i>Error al cargar información del servicio';
                } else {
                    const precio = new Intl.NumberFormat('es-CL', {
                        style: 'currency',
                        currency: 'CLP'
                    }).format(data.precio);
                    
                    servicioInfo.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center mt-2">
                            <span class="badge bg-success fs-6">
                                <i class="fas fa-dollar-sign me-1"></i>Precio: ${precio}
                            </span>
                            <span class="badge bg-info fs-6">
                                <i class="fas fa-clock me-1"></i>Duración: ${data.duracion} min
                            </span>
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                servicioInfo.innerHTML = '<i class="fas fa-exclamation-circle text-danger me-1"></i>Error al cargar información del servicio';
            });
    }

    // Event listeners
    console.log('🔗 Agregando event listeners...');
    fechaInput.addEventListener('change', function() {
        console.log('📅 Fecha cambiada:', fechaInput.value);
        cargarHorasDisponibles();
    });
    barberoSelect.addEventListener('change', function() {
        console.log('💇 Barbero cambiado:', barberoSelect.value);
        cargarHorasDisponibles();
    });
    servicioSelect.addEventListener('change', function() {
        console.log('✂️ Servicio cambiado:', servicioSelect.value);
        mostrarInfoServicio();
    });
    
    // Actualizar campo hidden cuando se selecciona una hora
    horaSelect.addEventListener('change', function() {
        horaHidden.value = horaSelect.value;
    });

    // Cargar información inicial si hay valores preseleccionados
    if (servicioSelect.value) {
        mostrarInfoServicio();
    }

    if (fechaInput.value && barberoSelect.value) {
        cargarHorasDisponibles();
    }

    // Validación del formulario antes de enviar
    const form = document.getElementById('reservaForm');
    form.addEventListener('submit', function(e) {
        const fecha = fechaInput.value;
        const barbero = barberoSelect.value;
        const servicio = servicioSelect.value;
        const hora = horaHidden.value;

        if (!fecha || !barbero || !servicio || !hora) {
            e.preventDefault();
            alert('Por favor completa todos los campos requeridos.');
            return false;
        }

        // Verificar que la fecha no sea en el pasado
        const fechaSeleccionada = new Date(fecha);
        const hoy = new Date();
        hoy.setHours(0, 0, 0, 0);

        if (fechaSeleccionada < hoy) {
            e.preventDefault();
            alert('No puedes reservar en una fecha pasada.');
            return false;
        }
    });
    
    return true;
    
    } catch (error) {
        console.error('💥 Error al inicializar reservas:', error);
        return false;
    }
}

// Múltiples formas de inicialización para asegurar que funcione
document.addEventListener('DOMContentLoaded', inicializarReservas);

// Fallback si DOMContentLoaded ya pasó
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarReservas);
} else {
    // DOM ya está listo
    setTimeout(inicializarReservas, 100);
}

// Fallback adicional
window.addEventListener('load', function() {
    setTimeout(inicializarReservas, 500);
});