// Enhanced Booking System - Fixed Time Selection
console.log('🚀 Enhanced Booking System v3.0 loaded');

class BookingFormController {
    constructor() {
        this.elements = {};
        this.state = {
            currentStep: 1,
            formData: {},
            isLoading: false,
            lastFetchParams: null,
            fetchTimeout: null
        };
        this.init();
    }

    init() {
        console.log('🔧 Initializing booking form controller...');
        
        // Get DOM elements
        this.elements = {
            fechaInput: document.getElementById('id_fecha'),
            barberoSelect: document.getElementById('id_barbero'),
            servicioSelect: document.getElementById('id_servicio'),
            horaSelect: document.getElementById('id_hora_select'),
            horaHidden: document.getElementById('id_hora_hidden'),
            servicioInfo: document.getElementById('servicio-info'),
            horarioSugerencia: document.getElementById('horario-sugerencia'),
            form: document.getElementById('reservaForm')
        };

        // Verify critical elements exist
        const missingElements = Object.keys(this.elements).filter(key => !this.elements[key]);
        if (missingElements.length > 0) {
            console.error('❌ Missing elements:', missingElements);
            return false;
        }

        console.log('✅ All elements found, setting up event listeners...');
        this.setupEventListeners();
        this.loadInitialData();
        return true;
    }

    setupEventListeners() {
        // Date change - reload available times with debounce
        this.elements.fechaInput.addEventListener('change', () => {
            console.log('📅 Date changed:', this.elements.fechaInput.value);
            this.updateStepCompletion('fecha');
            this.debouncedLoadAvailableTimes();
            this.updateProgress();
        });

        // Barber change - reload available times with debounce
        this.elements.barberoSelect.addEventListener('change', () => {
            console.log('💇 Barber changed:', this.elements.barberoSelect.value);
            this.updateStepCompletion('barbero');
            this.debouncedLoadAvailableTimes();
            this.updateProgress();
        });

        // Service change - show service info
        this.elements.servicioSelect.addEventListener('change', () => {
            console.log('✂️ Service changed:', this.elements.servicioSelect.value);
            this.updateStepCompletion('servicio');
            this.showServiceInfo();
            this.updateProgress();
        });

        // Time selection - update hidden field
        this.elements.horaSelect.addEventListener('change', () => {
            console.log('⏰ Time selected:', this.elements.horaSelect.value);
            this.elements.horaHidden.value = this.elements.horaSelect.value;
            this.updateStepCompletion('hora');
            this.validateForm();
            this.updateProgress();
        });

        // Form submission validation
        this.elements.form.addEventListener('submit', (e) => {
            if (!this.validateFormSubmission()) {
                e.preventDefault();
            }
        });
    }

    debouncedLoadAvailableTimes() {
        // Clear any pending timeout
        if (this.state.fetchTimeout) {
            clearTimeout(this.state.fetchTimeout);
        }

        // Set new timeout to prevent rapid-fire requests
        this.state.fetchTimeout = setTimeout(() => {
            this.loadAvailableTimes();
        }, 300); // Wait 300ms after last change
    }

    loadInitialData() {
        // Update visual selections for pre-selected values
        if (this.elements.barberoSelect.value) {
            const barberoCard = document.querySelector(`[data-barbero-id="${this.elements.barberoSelect.value}"]`);
            if (barberoCard) {
                barberoCard.classList.add('selected');
            }
            this.updateStepCompletion('barbero');
        }

        if (this.elements.servicioSelect.value) {
            const servicioCard = document.querySelector(`[data-service-id="${this.elements.servicioSelect.value}"]`);
            if (servicioCard) {
                servicioCard.classList.add('selected');
            }
            this.showServiceInfo();
            this.updateStepCompletion('servicio');
        }

        if (this.elements.fechaInput.value) {
            this.updateStepCompletion('fecha');
        }

        if (this.elements.horaHidden.value) {
            // Update visual selection for pre-selected time
            const timeSlot = document.querySelector(`[data-time="${this.elements.horaHidden.value}"]`);
            if (timeSlot) {
                timeSlot.classList.add('selected');
            }
            this.updateStepCompletion('hora');
        }

        // Load available times if date and barber are pre-selected
        if (this.elements.fechaInput.value && this.elements.barberoSelect.value) {
            this.loadAvailableTimes();
        }

        // Update initial progress
        this.updateProgress();
    }

    async loadAvailableTimes() {
        const fecha = this.elements.fechaInput.value;
        const barberoId = this.elements.barberoSelect.value;

        console.log('🔍 Loading times for:', { fecha, barberoId });

        // Check if we're already loading or if params haven't changed
        const currentParams = `${fecha}-${barberoId}`;
        if (this.state.isLoading) {
            console.log('⏸️ Already loading, skipping duplicate request');
            return;
        }
        
        if (this.state.lastFetchParams === currentParams) {
            console.log('⏸️ Same parameters, skipping duplicate request');
            return;
        }

        // Reset time selection
        this.elements.horaHidden.value = '';
        
        if (!fecha || !barberoId) {
            this.state.lastFetchParams = null;
            this.elements.horaSelect.innerHTML = '<option value="">Selecciona fecha y barbero primero</option>';
            this.elements.horaSelect.disabled = true;
            this.updateHorarioSugerencia('info', 'Selecciona fecha y barbero para ver horarios disponibles');
            
            // Show placeholder in grid
            const container = document.getElementById('time-slots-container');
            if (container) {
                container.innerHTML = `
                    <div class="time-slots-placeholder">
                        <i class="fas fa-clock text-muted"></i>
                        <p class="text-muted mb-0">Selecciona fecha y barbero para ver horarios disponibles</p>
                    </div>
                `;
            }
            return;
        }

        // Store current params to prevent duplicates
        this.state.lastFetchParams = currentParams;

        // Show loading state
        this.state.isLoading = true;
        this.elements.horaSelect.innerHTML = '<option value="">Cargando horarios disponibles...</option>';
        this.elements.horaSelect.disabled = true;
        this.updateHorarioSugerencia('info', 'Cargando horarios disponibles...');
        
        // Show loading in grid
        const container = document.getElementById('time-slots-container');
        if (container) {
            container.innerHTML = `
                <div class="time-slots-loading">
                    <i class="fas fa-spinner fa-spin"></i>
                    <p>Cargando horarios disponibles...</p>
                </div>
            `;
        }

        try {
            console.log('🌐 Fetching from:', `/horas-disponibles/?fecha=${fecha}&barbero=${barberoId}`);
            const response = await fetch(`/horas-disponibles/?fecha=${fecha}&barbero=${barberoId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('📊 Received time data:', data);

            this.populateTimeSlots(data.horas || []);
            
        } catch (error) {
            console.error('❌ Error loading available times:', error);
            this.state.lastFetchParams = null; // Reset to allow retry
            this.elements.horaSelect.innerHTML = '<option value="">Error al cargar horarios</option>';
            this.updateHorarioSugerencia('error', 'Error al cargar horarios. Intenta nuevamente.');
            
            // Show error in grid
            const container = document.getElementById('time-slots-container');
            if (container) {
                container.innerHTML = `
                    <div class="time-slots-empty">
                        <i class="fas fa-exclamation-triangle text-warning"></i>
                        <p>Error al cargar horarios</p>
                        <small class="text-muted">Intenta nuevamente en unos momentos</small>
                    </div>
                `;
            }
        } finally {
            this.state.isLoading = false;
        }
    }

    populateTimeSlots(horas) {
        console.log('⏰ Populating time slots:', horas);
        
        const container = document.getElementById('time-slots-container');
        if (!container) return;

        // Clear existing options in hidden select
        this.elements.horaSelect.innerHTML = '<option value="">Selecciona una hora</option>';

        if (!horas || horas.length === 0) {
            // Show empty state
            container.innerHTML = `
                <div class="time-slots-empty">
                    <i class="fas fa-calendar-times"></i>
                    <p>No hay horarios disponibles para esta fecha</p>
                    <small class="text-muted">Intenta con otra fecha</small>
                </div>
            `;
            this.elements.horaSelect.disabled = true;
            this.updateHorarioSugerencia('warning', 'No hay horarios disponibles para esta fecha');
            return;
        }

        // Create time slots grid
        const gridHTML = `
            <div class="time-slots-grid" role="radiogroup" aria-label="Seleccionar hora de la cita">
                ${horas.map(hora => `
                    <div class="time-slot available" 
                         data-time="${hora.value}" 
                         onclick="selectTimeSlot('${hora.value}')"
                         onkeydown="handleTimeSlotKeydown(event, '${hora.value}')"
                         tabindex="0"
                         role="radio"
                         aria-checked="false"
                         aria-label="Hora ${hora.text}">
                        ${hora.text}
                    </div>
                `).join('')}
            </div>
        `;

        container.innerHTML = gridHTML;

        // Add available time slots to hidden select
        horas.forEach(hora => {
            const option = document.createElement('option');
            option.value = hora.value;
            option.textContent = hora.text;
            this.elements.horaSelect.appendChild(option);
        });

        // Enable the select
        this.elements.horaSelect.disabled = false;
        this.updateHorarioSugerencia('success', `${horas.length} horarios disponibles`);
        
        console.log('✅ Time slots grid populated successfully');
    }

    async showServiceInfo() {
        const servicioId = this.elements.servicioSelect.value;

        if (!servicioId) {
            this.elements.servicioInfo.innerHTML = '';
            return;
        }

        console.log('💰 Loading service info for:', servicioId);

        try {
            const response = await fetch(`/info-servicio/?servicio_id=${servicioId}`);
            const data = await response.json();

            if (data.error) {
                this.elements.servicioInfo.innerHTML = '<div class="text-danger small">Error al cargar información del servicio</div>';
                return;
            }

            const precio = new Intl.NumberFormat('es-CL', {
                style: 'currency',
                currency: 'CLP'
            }).format(data.precio);

            this.elements.servicioInfo.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mt-2">
                    <span class="badge bg-success fs-6">
                        <i class="fas fa-dollar-sign me-1"></i>Precio: ${precio}
                    </span>
                    <span class="badge bg-info fs-6">
                        <i class="fas fa-clock me-1"></i>Duración: ${data.duracion} min
                    </span>
                </div>
            `;

        } catch (error) {
            console.error('❌ Error loading service info:', error);
            this.elements.servicioInfo.innerHTML = '<div class="text-danger small">Error al cargar información del servicio</div>';
        }
    }

    updateHorarioSugerencia(type, message) {
        const icons = {
            info: 'fas fa-info-circle',
            success: 'fas fa-check-circle',
            warning: 'fas fa-exclamation-triangle',
            error: 'fas fa-exclamation-circle'
        };

        // Remove existing type classes
        this.elements.horarioSugerencia.classList.remove('success', 'warning', 'error');
        
        // Add new type class
        if (type !== 'info') {
            this.elements.horarioSugerencia.classList.add(type);
        }

        this.elements.horarioSugerencia.innerHTML = `
            <i class="${icons[type]} me-1"></i>${message}
        `;
    }

    setLoadingState(isLoading) {
        this.state.isLoading = isLoading;
        // Could add visual loading indicators here
    }

    validateForm() {
        const fecha = this.elements.fechaInput.value;
        const barbero = this.elements.barberoSelect.value;
        const servicio = this.elements.servicioSelect.value;
        const hora = this.elements.horaHidden.value;

        const isValid = fecha && barbero && servicio && hora;
        
        // Update submit button state if needed
        const submitBtn = this.elements.form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = !isValid;
        }

        return isValid;
    }

    updateStepCompletion(step) {
        const checkIcon = document.getElementById(`${step}-check`);
        const stepIndicator = document.querySelector(`#step-${step === 'barbero' || step === 'servicio' ? '1' : '2'} .step-indicator`);
        
        let isCompleted = false;
        
        switch(step) {
            case 'barbero':
                isCompleted = !!this.elements.barberoSelect.value;
                break;
            case 'servicio':
                isCompleted = !!this.elements.servicioSelect.value;
                break;
            case 'fecha':
                isCompleted = !!this.elements.fechaInput.value;
                break;
            case 'hora':
                isCompleted = !!this.elements.horaHidden.value;
                break;
        }
        
        if (checkIcon) {
            if (isCompleted) {
                checkIcon.style.display = 'block';
                checkIcon.classList.add('fade-in');
            } else {
                checkIcon.style.display = 'none';
                checkIcon.classList.remove('fade-in');
            }
        }
        
        if (stepIndicator && isCompleted) {
            stepIndicator.classList.add('completed');
        } else if (stepIndicator) {
            stepIndicator.classList.remove('completed');
        }
    }

    updateProgress() {
        const progressBar = document.getElementById('booking-progress');
        if (!progressBar) return;
        
        let completedSteps = 0;
        const totalSteps = 4;
        
        if (this.elements.barberoSelect.value) completedSteps++;
        if (this.elements.servicioSelect.value) completedSteps++;
        if (this.elements.fechaInput.value) completedSteps++;
        if (this.elements.horaHidden.value) completedSteps++;
        
        const percentage = (completedSteps / totalSteps) * 100;
        progressBar.style.width = `${percentage}%`;
        
        // Update progress bar color based on completion
        if (percentage === 100) {
            progressBar.classList.remove('bg-primary');
            progressBar.classList.add('bg-success');
        } else {
            progressBar.classList.remove('bg-success');
            progressBar.classList.add('bg-primary');
        }
    }

    validateFormSubmission() {
        const fecha = this.elements.fechaInput.value;
        const barbero = this.elements.barberoSelect.value;
        const servicio = this.elements.servicioSelect.value;
        const hora = this.elements.horaHidden.value;

        if (!fecha || !barbero || !servicio || !hora) {
            this.showErrorMessage('Por favor completa todos los campos requeridos.');
            return false;
        }

        // Validate date is not in the past
        const fechaSeleccionada = new Date(fecha);
        const hoy = new Date();
        hoy.setHours(0, 0, 0, 0);

        if (fechaSeleccionada < hoy) {
            this.showErrorMessage('No puedes reservar en una fecha pasada.');
            return false;
        }

        return true;
    }

    showErrorMessage(message) {
        // Create or update error message
        let errorDiv = document.getElementById('booking-error-message');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = 'booking-error-message';
            errorDiv.className = 'alert alert-danger animated-error';
            this.elements.form.insertBefore(errorDiv, this.elements.form.firstChild);
        }
        
        errorDiv.innerHTML = `<i class="fas fa-exclamation-triangle me-2"></i>${message}`;
        errorDiv.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (errorDiv) {
                errorDiv.style.display = 'none';
            }
        }, 5000);
    }
}

// Barber selection function (global for onclick)
function selectBarber(barberId) {
    console.log('👨‍💼 Selecting barber:', barberId);
    
    // Update the hidden select
    const barberoSelect = document.getElementById('id_barbero');
    if (barberoSelect) {
        barberoSelect.value = barberId;
        
        // Trigger change event
        const event = new Event('change', { bubbles: true });
        barberoSelect.dispatchEvent(event);
    }
    
    // Update visual selection and accessibility
    document.querySelectorAll('.barber-card').forEach(card => {
        card.classList.remove('selected');
        card.setAttribute('aria-checked', 'false');
    });
    
    const selectedCard = document.querySelector(`[data-barbero-id="${barberId}"]`);
    if (selectedCard) {
        selectedCard.classList.add('selected');
        selectedCard.setAttribute('aria-checked', 'true');
    }
}

// Service selection function (global for onclick)
function selectService(serviceId) {
    console.log('✂️ Selecting service:', serviceId);
    
    // Update the hidden select
    const servicioSelect = document.getElementById('id_servicio');
    if (servicioSelect) {
        servicioSelect.value = serviceId;
        
        // Trigger change event
        const event = new Event('change', { bubbles: true });
        servicioSelect.dispatchEvent(event);
    }
    
    // Update visual selection and accessibility
    document.querySelectorAll('.service-card').forEach(card => {
        card.classList.remove('selected');
        card.setAttribute('aria-checked', 'false');
    });
    
    const selectedCard = document.querySelector(`[data-service-id="${serviceId}"]`);
    if (selectedCard) {
        selectedCard.classList.add('selected');
        selectedCard.setAttribute('aria-checked', 'true');
    }
}

// Time slot selection function (global for onclick)
function selectTimeSlot(timeValue) {
    console.log('⏰ Selecting time slot:', timeValue);
    
    // Update the hidden select and input
    const horaSelect = document.getElementById('id_hora_select');
    const horaHidden = document.getElementById('id_hora_hidden');
    
    if (horaSelect) {
        horaSelect.value = timeValue;
    }
    
    if (horaHidden) {
        horaHidden.value = timeValue;
        
        // Trigger change event
        const event = new Event('change', { bubbles: true });
        horaHidden.dispatchEvent(event);
    }
    
    // Update visual selection and accessibility
    document.querySelectorAll('.time-slot').forEach(slot => {
        slot.classList.remove('selected');
        slot.setAttribute('aria-checked', 'false');
    });
    
    const selectedSlot = document.querySelector(`[data-time="${timeValue}"]`);
    if (selectedSlot) {
        selectedSlot.classList.add('selected');
        selectedSlot.setAttribute('aria-checked', 'true');
    }
}

// Keyboard navigation for cards
function handleCardKeydown(event, id, type) {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (type === 'barber') {
            selectBarber(id);
        } else if (type === 'service') {
            selectService(id);
        }
    } else if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        event.preventDefault();
        navigateCards(event.target, 'next');
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        event.preventDefault();
        navigateCards(event.target, 'prev');
    }
}

// Navigate between cards with keyboard
function navigateCards(currentCard, direction) {
    const container = currentCard.closest('.barber-cards-container, .service-cards-container');
    if (!container) return;
    
    const cards = Array.from(container.querySelectorAll('[tabindex="0"]'));
    const currentIndex = cards.indexOf(currentCard);
    
    let nextIndex;
    if (direction === 'next') {
        nextIndex = (currentIndex + 1) % cards.length;
    } else {
        nextIndex = currentIndex === 0 ? cards.length - 1 : currentIndex - 1;
    }
    
    cards[nextIndex].focus();
}

// Keyboard navigation for time slots
function handleTimeSlotKeydown(event, timeValue) {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectTimeSlot(timeValue);
    } else if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        event.preventDefault();
        navigateTimeSlots(event.target, 'next');
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        event.preventDefault();
        navigateTimeSlots(event.target, 'prev');
    }
}

// Navigate between time slots with keyboard
function navigateTimeSlots(currentSlot, direction) {
    const container = currentSlot.closest('.time-slots-grid');
    if (!container) return;
    
    const slots = Array.from(container.querySelectorAll('.time-slot[tabindex="0"]'));
    const currentIndex = slots.indexOf(currentSlot);
    
    let nextIndex;
    if (direction === 'next') {
        nextIndex = (currentIndex + 1) % slots.length;
    } else {
        nextIndex = currentIndex === 0 ? slots.length - 1 : currentIndex - 1;
    }
    
    slots[nextIndex].focus();
}

// Mobile touch enhancements
function initializeMobileEnhancements() {
    // Add touch feedback for mobile devices
    if ('ontouchstart' in window) {
        document.addEventListener('touchstart', function(e) {
            const target = e.target.closest('.barber-card, .service-card, .time-slot');
            if (target) {
                target.style.transform = 'scale(0.98)';
            }
        });
        
        document.addEventListener('touchend', function(e) {
            const target = e.target.closest('.barber-card, .service-card, .time-slot');
            if (target) {
                setTimeout(() => {
                    target.style.transform = '';
                }, 150);
            }
        });
    }
    
    // Improve form accessibility
    const formElements = document.querySelectorAll('input, select, button');
    formElements.forEach(element => {
        element.addEventListener('focus', function() {
            this.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
    });
}

// Initialize when DOM is ready
function initializeBookingSystem() {
    console.log('🎯 Initializing booking system...');
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new BookingFormController();
            initializeMobileEnhancements();
        });
    } else {
        new BookingFormController();
        initializeMobileEnhancements();
    }
}

// Multiple initialization attempts to ensure it works
initializeBookingSystem();

// Fallback initialization
window.addEventListener('load', () => {
    setTimeout(() => {
        if (!window.bookingController) {
            console.log('🔄 Fallback initialization...');
            window.bookingController = new BookingFormController();
        }
    }, 500);
});