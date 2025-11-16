from django.core.exceptions import ValidationError
from django.db import transaction
import random
from .models import Session, Player, Result, Phase, Role


SPORT_MODE_KEYWORD = "спортив"   # подстрока в названии спортивного режима


# === 1. Подбор ролей под количество игроков ===

def build_default_role_pool(players_count: int) -> list[Role]:
    """
    Набор ролей для классики по описанным правилам:

    - мафия ≈ 25% от игроков, минимум 2;
    - комиссар — всегда, если игроков >= 6;
    - доктор — с 8 игроков;
    - дон мафии (это тоже мафия) — с 12 игроков;
    - маньяк — с 13 игроков;
    - красотка — с 14 игроков;
    - остальные — мирные жители.
    """
    roles_by_name = {r.name.lower(): r for r in Role.objects.all()}

    mafia_role = roles_by_name.get("мафия")
    town_role = roles_by_name.get("мирный житель")
    cop_role = roles_by_name.get("комиссар")
    doctor_role = roles_by_name.get("доктор")
    don_role = roles_by_name.get("дон мафии")
    maniac_role = roles_by_name.get("маньяк")
    beauty_role = roles_by_name.get("красотка")

    pool: list[Role] = []

    # --- мафия (25% от игроков, минимум 2) ---
    mafia_total = 0
    if mafia_role or don_role:
        mafia_total = max(2, int(players_count * 0.25 + 0.5))  # ~25%, округление вверх

        # дон появляется с 12 игроков и считается одной из мафий
        don_slots = 1 if (don_role and players_count >= 12 and mafia_total >= 2) else 0

        simple_mafia_count = max(mafia_total - don_slots, 0)
        if mafia_role and simple_mafia_count > 0:
            pool.extend([mafia_role] * simple_mafia_count)

        if don_slots:
            pool.append(don_role)

    # особые роли (кроме мафии)
    # комиссар — с 6 игроков
    if cop_role and players_count >= 6:
        pool.append(cop_role)

    # доктор — с 8 игроков
    if doctor_role and players_count >= 8:
        pool.append(doctor_role)

    # маньяк — с 13
    if maniac_role and players_count >= 13:
        pool.append(maniac_role)

    # красотка — с 14
    if beauty_role and players_count >= 14:
        pool.append(beauty_role)

    # добиваем мирными
    if town_role:
        remaining = players_count - len(pool)
        if remaining > 0:
            pool.extend([town_role] * remaining)

    # на всякий — обрезаем, если вдруг переложили
    return pool[:players_count]


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

    roles_pool = (
        [peaceful] * 6 +
        [cop] +
        [mafia] * 2 +
        [don]
    )

    random.shuffle(players)
    random.shuffle(roles_pool)

    for player, role in zip(players, roles_pool):
        player.role = role
        player.save()


def assign_roles_randomly(session, players):
    """
    Раздача ролей:
    - для спортивной мафии — жёсткая схема (assign_roles_sport);
    - для остальных режимов — по build_default_role_pool().
    """
    players = list(players)
    if not players:
        return

    mode_name = session.mode.name.lower()

    # спортивный режим
    if SPORT_MODE_KEYWORD in mode_name:
        return assign_roles_sport(session, players)

    # обычные режимы
    pool = build_default_role_pool(len(players))
    if not pool:
        # запасной вариант — просто крутим все роли
        roles = list(Role.objects.all())
        if not roles:
            return
        random.shuffle(roles)
        pool = roles * ((len(players) // len(roles)) + 1)

    random.shuffle(players)
    random.shuffle(pool)

    for player, role in zip(players, pool):
        player.role = role
        player.save()


# Подсчёт живых и определение победителя

def get_alive_players(session: Session):
    return Player.objects.filter(
        session=session,
        status=Player.PlayerStatus.ALIVE,
    ).select_related("role")


def get_alive_counts(session: Session) -> tuple[int, int, int]:
    """
    Возвращает (mafia_count, town_count, maniac_count).

    - Дон мафии считается мафией (по подстроке "маф");
    - Маньяк — отдельная третья сторона;
    - Остальные — мирные (включая доктора, комиссара, красотку и т.п.).
    """
    alive = list(get_alive_players(session))
    mafia = town = maniac = 0

    for p in alive:
        role_name = (p.role.name if p.role else "").lower()

        if "маньяк" in role_name:
            maniac += 1
        elif "маф" in role_name:  # "мафия" и "дон мафии"
            mafia += 1
        else:
            town += 1

    return mafia, town, maniac


def check_winner(session: Session) -> str | None:
    """
    Победитель по правилам:
    - если жив только маньяк → побеждает Маньяк;
    - если мафии и маньяка нет, но есть мирные → побеждают Мирные;
    - если есть только мафия (дон считается мафией), без мирных и маньяка → побеждает Мафия;
    - во всех остальных случаях игра продолжается.
    """
    mafia, town, maniac = get_alive_counts(session)

    # Маньяк один
    if maniac > 0 and mafia == 0 and town == 0:
        return Result.WinnerSide.MANIAC

    # Мирные победили: мафии и маньяка нет
    if mafia == 0 and maniac == 0 and town > 0:
        return Result.WinnerSide.TOWN

    # Мафия победила: остались только мафия/дон
    if mafia > 0 and town == 0 and maniac == 0:
        return Result.WinnerSide.MAFIA

    # Игра продолжается
    return None


# 3. Переход по фазам

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

    # если фаза не установлена — ставим первую
    if session.current_phase is None:
        session.current_phase = phases[0]
        session.save()
        return

    # ищем индекс текущей фазы
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
            mafia_count, town_count, _ = get_alive_counts(session)
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

        # если победителя нет — новый круг, с первой фазы
        session.current_round += 1
        session.current_phase = phases[0]
        session.save()
    else:
        # просто идём к следующей фазе
        session.current_phase = phases[idx + 1]
        session.save()
