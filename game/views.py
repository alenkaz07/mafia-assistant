from django.shortcuts import render
from .models import Session, Result, Role, Mode

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

def rules(request):
    return render(request, 'game/rules.html')


def roles(request):
    roles = Role.objects.all()
    return render(request, 'game/roles.html', {'roles': roles})


def modes(request):
    modes = Mode.objects.all()
    return render(request, 'game/modes.html', {'modes': modes})


def sessions_list(request):
    sessions = Session.objects.all().order_by('-created_at')
    return render(request, 'game/sessions_list.html', {'sessions': sessions})

def sitemap(request):
    return render(request, 'game/sitemap.html')
