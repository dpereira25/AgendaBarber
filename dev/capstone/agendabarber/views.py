from django.shortcuts import render

# Create your views here.

def cargarBase(request):
    return render(request, 'base.html')


def cargarCatalogo(request):
    # Ejemplo: lista de cortes de pelo (luego vendrá de la base de datos)
    cortes = [
        {'nombre': 'Mid fade', 'precio': 7000, 'imagen': 'agendabarber/img/midfade.jpg'},
        {'nombre': 'Fade alto', 'precio': 7000, 'imagen': 'agendabarber/img/fadealto.jpg'},
        {'nombre': 'Burst fade', 'precio': 7000, 'imagen': 'agendabarber/img/burstfade.jpg'},
        {'nombre': 'Buzz cut', 'precio': 7000, 'imagen': 'agendabarber/img/buzzcut.jpg'},
    ]
    return render(request, 'catalogo.html', {'cortes': cortes})
