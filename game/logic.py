from django.core.exceptions import ValidationError
from django.db import transaction
import random
from .models import Session, Player, Result, Phase, Role

SPORT_MODE_KEYWORD = "спортив"  # подстрока в названии режима

def build_default_role_pool(players_count: int) -> list[Role]:
    """
    Простейшая рекомендация набора ролей по количеству игроков.
    """
    all_roles = {r.name.lower(): r for r in Role.objects.all()}
    mafia = all_roles.get("мафия") or all_roles.get("мафиози")
    town = all_roles.get("мирный житель")
    commissar = all_roles.get("комиссар")
    doctor = all_roles.get("доктор")

    pool: list[Role] = []

    if players_count <= 9:
        mafia_count = 2
        town = 3
        commissar = 1
    elif players_count <= 9:
        mafia_count = 2
    else:
        mafia_count = 3

    if mafia:
        pool.extend([mafia] * mafia_count)

    if town:
        town_count = max(players_count - mafia_count - 2, 0)
        pool.extend([town] * town_count)

    if commissar and players_count >= 6:
        pool.append(commissar)
    if doctor and players_count >= 7:
        pool.append(doctor)

    while len(pool) < players_count and town:
        pool.append(town)

    return pool


def assign_roles_randomly(session, players):
    """
    Раздача ролей:
    - для спортивной мафии — по жёсткой схеме;
    - для остальных режимов — просто рандом из всех ролей.
    """
    mode_name = session.mode.name.lower()

    if SPORT_MODE_KEYWORD in mode_name:
        return assign_roles_sport(session, players)

    # Обычный режим — просто случайные роли из всех доступных
    roles = list(Role.objects.all())
    if not roles:
        return

    random.shuffle(roles)
    roles_cycle = roles * ((len(players) // len(roles)) + 1)

    for player, role in zip(players, roles_cycle):
        player.role = role
        player.save()

def assign_roles_sport(session, players):
    """
    Спортивная мафия: ровно 10 игроков и фиксированный набор ролей:
    6 мирных, 1 комиссар, 2 мафии, 1 дон.
    """
    players = list(players)
    if len(players) != 10:
        raise ValidationError(
            f"Для спортивной мафии нужно ровно 10 игроков, сейчас их {len(players)}."
        )

    # Ищем роли по названиям
    try:
        peaceful = Role.objects.get(name="Мирный житель")
        cop = Role.objects.get(name="Комиссар")
        mafia = Role.objects.get(name="Мафия")
        don = Role.objects.get(name="Дон мафии")
    except Role.DoesNotExist as e:
        raise ValidationError(f"Не найдена одна из ролей для спортивной мафии: {e}")

    # Жёсткий пул ролей: 10 штук
    roles_pool = (
        [peaceful] * 6 +
        [cop] * 1 +
        [mafia] * 2 +
        [don] * 1
    )

    random.shuffle(players)
    random.shuffle(roles_pool)

    for player, role in zip(players, roles_pool):
        player.role = role
        player.save()

def get_alive_players(session: Session):
    return Player.objects.filter(
        session=session,
        status=Player.PlayerStatus.ALIVE
    ).select_related("role")


def get_alive_counts(session: Session) -> tuple[int, int]:
    alive = list(get_alive_players(session))
    mafia = sum(1 for p in alive if "маф" in p.role.name.lower())
    town = len(alive) - mafia
    return mafia, town


def check_winner(session: Session) -> str | None:
    mafia_count, town_count = get_alive_counts(session)

    if mafia_count == 0:
        return Result.WinnerSide.TOWN
    if mafia_count >= town_count:
        return Result.WinnerSide.MAFIA
    return None  # игра продолжается


@transaction.atomic
def advance_phase(session: Session):
    """
    Переход на следующую фазу:
      - фазы берём из Phase.order,
      - на последней фазе круга проверяем победителя.
    """
    phases = list(Phase.objects.order_by("order"))
    if not phases:
        return

    if session.current_phase is None:
        session.current_phase = phases[0]
        session.save()
        return

    try:
        idx = phases.index(session.current_phase)
    except ValueError:
        session.current_phase = phases[0]
        session.save()
        return

    is_last_phase = (idx == len(phases) - 1)

    if is_last_phase:
        winner = check_winner(session)
        if winner and session.status != Session.Status.FINISHED:
            mafia_count, town_count = get_alive_counts(session)
            Result.objects.create(
                session=session,
                winner_side=winner,
                rounds_count=session.current_round,
                mafia_count=mafia_count,
                town_count=town_count,
            )
            session.status = Session.Status.FINISHED
            session.save()
            return

        session.current_round += 1
        session.current_phase = phases[0]
        session.save()
    else:
        session.current_phase = phases[idx + 1]
        session.save()
