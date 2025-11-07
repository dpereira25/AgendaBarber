"""
Middleware for AgendaBarber application.
Includes automatic cleanup functionality.
"""

from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import random
import logging

logger = logging.getLogger(__name__)


class AutoCleanupMiddleware:
    """
    Middleware that periodically triggers cleanup of expired temporary reservations.
    Uses probabilistic triggering to avoid performance issues.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Probability of triggering cleanup on each request (1 in 100 requests)
        self.cleanup_probability = 0.01
        # Minimum time between cleanup attempts (5 minutes)
        self.cleanup_interval = timedelta(minutes=5)
        self.cache_key = 'last_auto_cleanup'
    
    def __call__(self, request):
        # Trigger cleanup before processing the request (if needed)
        self.maybe_trigger_cleanup()
        
        response = self.get_response(request)
        
        return response
    
    def maybe_trigger_cleanup(self):
        """
        Maybe trigger cleanup based on probability and time since last cleanup.
        """
        # Check if we should attempt cleanup (probabilistic)
        if random.random() > self.cleanup_probability:
            return
        
        # Check if enough time has passed since last cleanup
        last_cleanup = cache.get(self.cache_key)
        now = timezone.now()
        
        if last_cleanup and (now - last_cleanup) < self.cleanup_interval:
            return
        
        # Trigger cleanup in a separate thread to avoid blocking the request
        try:
            from .services.cleanup_service import CleanupService
            
            # Only clean up temporary reservations (quick operation)
            result = CleanupService.cleanup_expired_temporary_reservations()
            
            if result['success'] and result['expired_cleaned'] > 0:
                logger.info(f"Auto-cleanup: {result['message']}")
            
            # Update last cleanup time
            cache.set(self.cache_key, now, timeout=3600)  # Cache for 1 hour
            
        except Exception as e:
            logger.error(f"Auto-cleanup failed: {str(e)}")


class TemporaryReservationCleanupMixin:
    """
    Mixin that can be added to views to trigger cleanup when appropriate.
    """
    
    def dispatch(self, request, *args, **kwargs):
        # Trigger cleanup before processing reservation-related views
        if hasattr(self, 'should_trigger_cleanup') and self.should_trigger_cleanup():
            self.trigger_cleanup()
        
        return super().dispatch(request, *args, **kwargs)
    
    def should_trigger_cleanup(self):
        """
        Override this method to define when cleanup should be triggered.
        Default: trigger on GET requests to availability-related views.
        """
        return self.request.method == 'GET'
    
    def trigger_cleanup(self):
        """
        Trigger cleanup of expired temporary reservations.
        """
        try:
            from .services.cleanup_service import CleanupService
            CleanupService.cleanup_expired_temporary_reservations()
        except Exception as e:
            logger.error(f"Cleanup trigger failed: {str(e)}")