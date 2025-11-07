"""
Service for periodic cleanup tasks related to temporary reservations and other maintenance.
"""

from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from ..models import TemporaryReservation, PaymentWebhookLog
from .temporary_reservation_service import TemporaryReservationService
import logging

logger = logging.getLogger(__name__)


class CleanupService:
    """Service for handling periodic cleanup tasks"""
    
    @classmethod
    def cleanup_expired_temporary_reservations(cls):
        """
        Clean up expired temporary reservations.
        
        Returns:
            dict: Cleanup results with counts and details
        """
        try:
            expired_count = TemporaryReservationService.cleanup_expired_reservations()
            
            result = {
                'success': True,
                'expired_cleaned': expired_count,
                'timestamp': timezone.now(),
                'message': f'Cleaned up {expired_count} expired temporary reservations'
            }
            
            if expired_count > 0:
                logger.info(result['message'])
            
            return result
            
        except Exception as e:
            error_msg = f'Error during temporary reservation cleanup: {str(e)}'
            logger.error(error_msg)
            
            return {
                'success': False,
                'expired_cleaned': 0,
                'timestamp': timezone.now(),
                'error': error_msg
            }
    
    @classmethod
    def cleanup_old_webhook_logs(cls, days_to_keep=30):
        """
        Clean up old webhook logs to prevent database bloat.
        
        Args:
            days_to_keep (int): Number of days of logs to keep
            
        Returns:
            dict: Cleanup results
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days_to_keep)
            
            old_logs = PaymentWebhookLog.objects.filter(received_at__lt=cutoff_date)
            deleted_count = old_logs.count()
            old_logs.delete()
            
            result = {
                'success': True,
                'logs_cleaned': deleted_count,
                'timestamp': timezone.now(),
                'message': f'Cleaned up {deleted_count} old webhook logs (older than {days_to_keep} days)'
            }
            
            if deleted_count > 0:
                logger.info(result['message'])
            
            return result
            
        except Exception as e:
            error_msg = f'Error during webhook log cleanup: {str(e)}'
            logger.error(error_msg)
            
            return {
                'success': False,
                'logs_cleaned': 0,
                'timestamp': timezone.now(),
                'error': error_msg
            }
    
    @classmethod
    def full_cleanup(cls):
        """
        Perform all cleanup tasks.
        
        Returns:
            dict: Combined results of all cleanup tasks
        """
        results = {
            'timestamp': timezone.now(),
            'tasks': {}
        }
        
        # Clean up temporary reservations
        temp_result = cls.cleanup_expired_temporary_reservations()
        results['tasks']['temporary_reservations'] = temp_result
        
        # Clean up old webhook logs
        webhook_result = cls.cleanup_old_webhook_logs()
        results['tasks']['webhook_logs'] = webhook_result
        
        # Calculate overall success
        results['success'] = all(
            task_result['success'] 
            for task_result in results['tasks'].values()
        )
        
        # Create summary message
        total_temp_cleaned = temp_result['expired_cleaned']
        total_logs_cleaned = webhook_result['logs_cleaned']
        
        results['summary'] = (
            f'Cleanup completed: {total_temp_cleaned} temp reservations, '
            f'{total_logs_cleaned} webhook logs'
        )
        
        logger.info(results['summary'])
        
        return results
    
    @classmethod
    def get_cleanup_stats(cls):
        """
        Get statistics about items that need cleanup.
        
        Returns:
            dict: Statistics about cleanup candidates
        """
        now = timezone.now()
        
        # Count expired temporary reservations
        expired_temp_count = TemporaryReservation.objects.expired().count()
        
        # Count active temporary reservations
        active_temp_count = TemporaryReservation.objects.active().count()
        
        # Count old webhook logs (older than 30 days)
        old_webhook_cutoff = now - timedelta(days=30)
        old_webhook_count = PaymentWebhookLog.objects.filter(
            received_at__lt=old_webhook_cutoff
        ).count()
        
        # Count recent webhook logs
        recent_webhook_count = PaymentWebhookLog.objects.filter(
            received_at__gte=old_webhook_cutoff
        ).count()
        
        return {
            'timestamp': now,
            'temporary_reservations': {
                'expired': expired_temp_count,
                'active': active_temp_count,
                'total': expired_temp_count + active_temp_count
            },
            'webhook_logs': {
                'old': old_webhook_count,
                'recent': recent_webhook_count,
                'total': old_webhook_count + recent_webhook_count
            },
            'needs_cleanup': expired_temp_count > 0 or old_webhook_count > 0
        }


class AutoCleanupMixin:
    """
    Mixin to add automatic cleanup functionality to views or other classes.
    Can be used to trigger cleanup on certain actions.
    """
    
    def trigger_cleanup_if_needed(self, force=False):
        """
        Trigger cleanup if needed based on certain conditions.
        
        Args:
            force (bool): Force cleanup regardless of conditions
            
        Returns:
            dict or None: Cleanup results if cleanup was performed
        """
        if force:
            return CleanupService.full_cleanup()
        
        # Get stats to decide if cleanup is needed
        stats = CleanupService.get_cleanup_stats()
        
        # Trigger cleanup if there are expired items
        if stats['needs_cleanup']:
            return CleanupService.full_cleanup()
        
        return None