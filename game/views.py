from django.shortcuts import render
from .models import Sessions, Results

# Create your views here.

def index(request):
    sessions_count = Sessions.objects.count()
    mafia_wins = Results.objects.filter(winner_side='mafia').count()
    town_wins = Results.objects.filter(winner_side='town').count()

    context = {
        'sessions_count': sessions_count,
        'mafia_wins': mafia_wins,
        'town_wins': town_wins,
    }
    return render(request, 'game/index.html', context)
