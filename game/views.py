from django.shortcuts import render, get_object_or_404, redirect
from .models import Session, Result, Role, Mode, Player
from .forms import SessionForm, PlayerForm


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
        .order_by('-id')
    )
    return render(request, 'game/sessions_list.html', {'sessions': sessions_qs})


def sitemap(request):
    """Карта сайта."""
    return render(request, 'game/sitemap.html')

# кабинет ведущего
def host_sessions(request):
    """
    Панель ведущего: список игровых сессий,
    с которыми он может работать.
    Пока без фильтрации по host — показываем все.
    """
    sessions_qs = (
        Session.objects
        .select_related('mode', 'host')
        .order_by('-created_at')
    )
    return render(request, 'game/host_sessions.html', {'sessions': sessions_qs})


def session_create(request):
    """
    Создание новой игровой сессии.
    """
    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)

            if request.user.is_authenticated:
                session.host = request.user
            session.save()
            return redirect('game:session_manage', session_id=session.id)
    else:
        form = SessionForm()

    return render(request, 'game/session_form.html', {'form': form})


def session_manage(request, session_id):
    """
    Управление конкретной сессией:
    список игроков, действия над ними.
    """
    session = get_object_or_404(
        Session.objects.select_related('mode'),
        id=session_id
    )
    players_qs = session.players.select_related('role').order_by('seat_number', 'name')

    context = {
        'session': session,
        'players': players_qs,
    }
    return render(request, 'game/session_manage.html', context)


def player_add(request, session_id):
    """
    Добавление игрока в выбранную сессию.
    """
    session = get_object_or_404(Session, id=session_id)

    if request.method == 'POST':
        form = PlayerForm(request.POST)
        if form.is_valid():
            player = form.save(commit=False)
            player.session = session
            player.save()
            return redirect('game:session_manage', session_id=session.id)
    else:
        form = PlayerForm()

    context = {
        'session': session,
        'form': form,
    }
    return render(request, 'game/player_form.html', context)


def player_toggle_status(request, session_id, player_id):
    """
    Переключить статус игрока: alive <-> dead.
    Удобно для фиксации выбывших по ходу игры.
    """
    session = get_object_or_404(Session, id=session_id)
    player = get_object_or_404(Player, id=player_id, session=session)

    if player.status == Player.PlayerStatus.ALIVE:
        player.status = Player.PlayerStatus.DEAD
    else:
        player.status = Player.PlayerStatus.ALIVE

    player.save()
    return redirect('game:session_manage', session_id=session.id)

def custom_404(request, exception):
    return render(request, 'game/404.html', status=404)
