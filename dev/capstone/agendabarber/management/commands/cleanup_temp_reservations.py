"""
Django management command to clean up expired temporary reservations.
This command should be run periodically (e.g., every 5-10 minutes) via cron or task scheduler.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from agendabarber.models import TemporaryReservation
from agendabarber.services.temporary_reservation_service import TemporaryReservationService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up expired temporary reservations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about cleanup process',
        )
        parser.add_argument(
            '--older-than-minutes',
            type=int,
            default=0,
            help='Clean up reservations older than specified minutes (0 = only expired)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        older_than_minutes = options['older_than_minutes']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting temporary reservation cleanup...')
        )
        
        # Get expired reservations
        if older_than_minutes > 0:
            cutoff_time = timezone.now() - timezone.timedelta(minutes=older_than_minutes)
            expired_reservations = TemporaryReservation.objects.filter(
                created_at__lt=cutoff_time
            )
            self.stdout.write(f'Looking for reservations older than {older_than_minutes} minutes')
        else:
            expired_reservations = TemporaryReservation.objects.expired()
            self.stdout.write('Looking for expired reservations')
        
        expired_count = expired_reservations.count()
        
        if expired_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No expired temporary reservations found.')
            )
            return
        
        if verbose or dry_run:
            self.stdout.write(f'Found {expired_count} expired temporary reservations:')
            for reservation in expired_reservations:
                time_info = f"Created: {reservation.created_at}, Expires: {reservation.expires_at}"
                self.stdout.write(
                    f'  - ID: {reservation.id} | {reservation.cliente_email} | '
                    f'{reservation.barbero.nombre} | {reservation.inicio} | {time_info}'
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would delete {expired_count} reservations')
            )
            return
        
        # Perform cleanup
        try:
            if older_than_minutes > 0:
                # Manual deletion for custom time range
                deleted_count = expired_reservations.count()
                expired_reservations.delete()
            else:
                # Use the service method for standard cleanup
                deleted_count = TemporaryReservationService.cleanup_expired_reservations()
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully cleaned up {deleted_count} expired temporary reservations')
            )
            
            # Log the cleanup
            logger.info(f'Cleaned up {deleted_count} expired temporary reservations')
            
        except Exception as e:
            error_msg = f'Error during cleanup: {str(e)}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            raise
        
        # Show remaining active reservations if verbose
        if verbose:
            active_count = TemporaryReservation.objects.active().count()
            self.stdout.write(f'Remaining active temporary reservations: {active_count}')
            
            if active_count > 0:
                self.stdout.write('Active reservations:')
                for reservation in TemporaryReservation.objects.active():
                    remaining_time = reservation.time_remaining
                    self.stdout.write(
                        f'  - ID: {reservation.id} | {reservation.cliente_email} | '
                        f'{reservation.barbero.nombre} | {reservation.inicio} | '
                        f'Expires in: {remaining_time}'
                    )