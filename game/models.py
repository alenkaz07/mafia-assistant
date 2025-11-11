from django.db import models

# Create your models here.

from django.contrib.auth.models import User


class Mode(models.Model):
    """Режим игры (классическая, спортивная и т.п.)."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    min_players = models.IntegerField()
    max_players = models.IntegerField()

    def __str__(self):
        return self.name


class Role(models.Model):
    """Игровые роли: мафия, мирный, комиссар и т.д."""
    name = models.CharField(max_length=100)
    description = models.TextField()
    is_unique = models.BooleanField(default=False)
    turn_order = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name


class Session(models.Model):
    """Игровая сессия (отдельная партия/вечер)."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Запланирована"
        ACTIVE = "active", "Идёт"
        FINISHED = "finished", "Завершена"

    mode = models.ForeignKey(Mode, on_delete=models.PROTECT, related_name="sessions")
    host = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="hosted_sessions"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    players_count = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Сессия #{self.id} ({self.mode.name})"


class Phase(models.Model):
    """Фазы игры: ночь, день, голосование."""

    name = models.CharField(max_length=100)
    order = models.IntegerField(help_text="Порядок внутри круга (1 – ночь, 2 – день и т.п.)")

    def __str__(self):
        return self.name


class Player(models.Model):
    """Конкретный игрок в рамках сессии."""

    class PlayerStatus(models.TextChoices):
        ALIVE = "alive", "В игре"
        DEAD = "dead", "Выбыл"

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="players")
    name = models.CharField(max_length=100)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="players")
    status = models.CharField(
        max_length=10, choices=PlayerStatus.choices, default=PlayerStatus.ALIVE
    )
    seat_number = models.IntegerField(null=True, blank=True)
    fail_phase = models.ForeignKey(
        Phase, on_delete=models.SET_NULL, null=True, blank=True, related_name="failed_players"
    )
    notes = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"{self.name} ({self.session_id})"


class Vote(models.Model):
    """Голос одного игрока против другого в конкретной фазе."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="votes")
    phase = models.ForeignKey(Phase, on_delete=models.PROTECT, related_name="votes")
    round_number = models.IntegerField(help_text="Номер круга/дня")
    voter = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="given_votes")
    target = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="received_votes")

    def __str__(self):
        return f"Голос {self.voter} против {self.target} (круг {self.round_number})"


class Result(models.Model):
    """Итоги партии."""

    class WinnerSide(models.TextChoices):
        MAFIA = "mafia", "Мафия"
        TOWN = "town", "Мирные"

    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name="result")
    winner_side = models.CharField(max_length=10, choices=WinnerSide.choices)
    rounds_count = models.IntegerField()
    mafia_count = models.IntegerField()
    town_count = models.IntegerField()

    def __str__(self):
        return f"Результат сессии #{self.session_id}"
