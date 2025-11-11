from django.shortcuts import render
from .models import Session, Result

# Create your views here.

def index(request):
    sessions_count = Session.objects.count()
    mafia_wins = Result.objects.filter(winner_side='mafia').count()
    town_wins = Result.objects.filter(winner_side='town').count()

    context = {
        'sessions_count': sessions_count,
        'mafia_wins': mafia_wins,
        'town_wins': town_wins,
    }
    return render(request, 'game/index.html', context)
