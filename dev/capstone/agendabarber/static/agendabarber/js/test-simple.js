// Test simple para verificar carga de JavaScript
console.log('🧪 TEST: JavaScript simple cargado correctamente');
alert('JavaScript funcionando!');

document.addEventListener('DOMContentLoaded', function() {
    console.log('🧪 TEST: DOM cargado');
    
    // Buscar elementos básicos
    const servicioSelect = document.getElementById('id_servicio');
    if (servicioSelect) {
        console.log('✅ Elemento servicio encontrado');
        servicioSelect.addEventListener('change', function() {
            console.log('🧪 TEST: Servicio cambiado a:', this.value);
            alert('Servicio seleccionado: ' + this.value);
        });
    } else {
        console.log('❌ Elemento servicio NO encontrado');
    }
});