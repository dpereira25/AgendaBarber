from django.core.management.base import BaseCommand
from agendabarber.models import Reserva

class Command(BaseCommand):
    help = 'Actualiza automáticamente los estados de las reservas basándose en la hora actual'

    def handle(self, *args, **options):
        reservas = Reserva.objects.all()
        actualizadas = 0

        for reserva in reservas:
            estado_anterior = reserva.estado
            reserva.actualizar_estado_automatico()
            
            if estado_anterior != reserva.estado:
                reserva.save()
                actualizadas += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Reserva {reserva.id}: {estado_anterior} -> {reserva.estado}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(f'✅ {actualizadas} reservas actualizadas')
        )
        
        # Mostrar estadísticas
        completadas = Reserva.objects.completadas().count()
        pendientes = Reserva.objects.pendientes().count()
        
        self.stdout.write(f'📊 Completadas: {completadas}')
        self.stdout.write(f'📊 Pendientes: {pendientes}')