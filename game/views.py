from django.shortcuts import render
from .models import Session, Result, Role, Mode


def index(request):
    """Главная страница с баннером и общей статистикой."""
    sessions_count = Session.objects.count()
    mafia_wins = Result.objects.filter(winner_side=Result.WinnerSide.MAFIA).count()
    town_wins = Result.objects.filter(winner_side=Result.WinnerSide.TOWN).count()

    context = {
        'sessions_count': sessions_count,
        'mafia_wins': mafia_wins,
        'town_wins': town_wins,
    }
    return render(request, 'game/index.html', context)


def rules(request):
    """Страница с правилами игры."""
    return render(request, 'game/rules.html')


def roles(request):
    """Справочник ролей."""
    roles_qs = Role.objects.all().order_by('name')
    return render(request, 'game/roles.html', {'roles': roles_qs})


def modes(request):
    """Справочник режимов игры."""
    modes_qs = Mode.objects.all().order_by('min_players')
    return render(request, 'game/modes.html', {'modes': modes_qs})


def sessions_list(request):
    """Список игровых сессий."""
    sessions_qs = (
        Session.objects
        .select_related('mode', 'host')
        .order_by('-created_at')
    )
    return render(request, 'game/sessions_list.html', {'sessions': sessions_qs})


def sitemap(request):
    """Карта сайта."""
    return render(request, 'game/sitemap.html')
