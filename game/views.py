from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError

from .models import Session, Result, Role, Mode, Player, Phase
from .forms import SessionForm, PlayerForm
from .logic import assign_roles_randomly, advance_phase, assign_roles_sport


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
    список игроков, переход по фазам.
    """
    session = get_object_or_404(
        Session.objects.select_related('mode', 'current_phase'),
        id=session_id
    )
    players_qs = session.players.select_related('role').order_by('seat_number', 'name')

    if request.method == 'POST' and 'advance_phase' in request.POST:
        advance_phase(session)
        return redirect('game:session_manage', session_id=session.id)

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
    Если помечаем DEAD — запоминаем фазу выбывания.
    """
    session = get_object_or_404(Session, id=session_id)
    player = get_object_or_404(Player, id=player_id, session=session)

    if player.status == Player.PlayerStatus.ALIVE:
        player.status = Player.PlayerStatus.DEAD
        player.fail_phase = session.current_phase
        player.fail_round = session.current_round
    else:
        player.status = Player.PlayerStatus.ALIVE
        player.fail_phase = None
        player.fail_round = None

    player.save()
    return redirect("game:session_manage", session_id=session.id)

def custom_404(request, exception):
    return render(request, 'game/404.html', status=404)

@require_POST
def session_delete(request, session_id):
    """
    Удаление сессии целиком (вместе с игроками, голосами, результатом).
    Вызывается и из списка сессий, и со страницы управления сессией.
    """
    session = get_object_or_404(Session, id=session_id)

    # if request.user != session.host and not request.user.is_superuser:
    #     return redirect('game:host_sessions')

    # Откуда вернуться после удаления
    next_url = request.POST.get('next') or reverse('game:host_sessions')

    session.delete()  # Players/Votes/Result удалятся по on_delete=CASCADE

    return redirect(next_url)

def session_start(request, session_id):
    """
    Старт игры:
    - проверяем, что сессия запланирована;
    - проверяем, что есть игроки;
    - проверяем, что фактическое кол-во игроков совпадает с запланированным;
    - для спортивной мафии — ровно 10 игроков и фиксированный набор ролей;
    - по выбору раздаём роли (рандом / вручную);
    - переводим сессию в ACTIVE и ставим первую фазу.
    """
    session = get_object_or_404(Session, id=session_id)

    # 1. Статус сессии
    if session.status != Session.Status.PLANNED:
        messages.warning(request, "Эта сессия уже запущена или завершена.")
        return redirect("game:session_manage", session_id=session.id)

    # 2. Игроки
    players_qs = session.players.all()
    players = list(players_qs)
    actual_players = len(players)
    planned_players = session.players_count or 0

    if actual_players == 0:
        messages.error(request, "Невозможно начать игру без игроков.")
        return redirect("game:session_manage", session_id=session.id)

    # Базовый минимум на всякий случай
    if actual_players < 6:
        messages.error(
            request,
            f"Нельзя начать игру: нужно минимум 6 игроков, сейчас их {actual_players}."
        )
        return redirect("game:session_manage", session_id=session.id)

    # 3. Проверка: фактическое количество игроков = запланированному
    if planned_players and actual_players != planned_players:
        messages.error(
            request,
            f"Нельзя начать игру: запланировано {planned_players} игроков, "
            f"сейчас добавлено {actual_players}."
        )
        return redirect("game:session_manage", session_id=session.id)

    # 4. Определяем, спортивная ли мафия
    is_sport_mode = (
        # по числам (min=max=10)
        (getattr(session.mode, "min_players", None) == 10
         and getattr(session.mode, "max_players", None) == 10)
        # и/или по названию
        and session.mode.name.lower() == "спортивная мафия"
    )

    # отдельная проверка для строгой 10
    if is_sport_mode and actual_players != 10:
        messages.error(
            request,
            f"Для спортивной мафии нужно ровно 10 игроков, сейчас их {actual_players}."
        )
        return redirect("game:session_manage", session_id=session.id)

    # 5. Способ выдачи ролей
    assign_mode = request.POST.get("assign_mode")  # "random" или "manual"

    if assign_mode == "random":
        try:
            if is_sport_mode:
                # Спортивная мафия: 6 мирных, 1 комиссар, 2 мафии, 1 дон
                assign_roles_sport(session, players)
            else:
                # Обычный общий рандом — только тем, у кого ещё нет роли
                players_without_role = [p for p in players if p.role_id is None]
                assign_roles_randomly(session, players_without_role)
        except ValidationError as e:
            # если в assign_roles_sport что-то пошло не так (нет ролей и т.п.)
            messages.error(request, str(e))
            return redirect("game:session_manage", session_id=session.id)

    # 6. Запускаем игру
    session.status = Session.Status.ACTIVE
    session.current_round = 1
    first_phase = Phase.objects.order_by("order").first()
    session.current_phase = first_phase
    session.save()

    messages.success(request, "Игра начата.")
    return redirect("game:session_manage", session_id=session.id)
