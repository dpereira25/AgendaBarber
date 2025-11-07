#!/usr/bin/env python
"""
Cron job script for cleaning up expired temporary reservations.

This script can be run periodically (e.g., every 5-10 minutes) to clean up
expired temporary reservations.

Usage:
    python scripts/cleanup_cron.py

Or add to crontab:
    */5 * * * * cd /path/to/project && python scripts/cleanup_cron.py

Environment variables needed:
    DJANGO_SETTINGS_MODULE=capstone.settings
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capstone.settings')
django.setup()

# Now we can import Django models and services
from agendabarber.services.cleanup_service import CleanupService
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main cleanup function"""
    try:
        logger.info("Starting scheduled cleanup...")
        
        # Perform cleanup
        result = CleanupService.cleanup_expired_temporary_reservations()
        
        if result['success']:
            if result['expired_cleaned'] > 0:
                logger.info(f"Cleanup successful: {result['message']}")
            else:
                logger.info("Cleanup completed: No expired reservations found")
        else:
            logger.error(f"Cleanup failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Cleanup script failed: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()