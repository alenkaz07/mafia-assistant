from django.db import models
from django.contrib.auth.models import User


class Mode(models.Model):
    """Режим игры (классическая, спортивная и т.п.)."""
    name = models.CharField("Название режима", max_length=100)
    description = models.TextField("Описание", blank=True)
    min_players = models.PositiveIntegerField("Минимум игроков")
    max_players = models.PositiveIntegerField("Максимум игроков")

    class Meta:
        verbose_name = "Режим игры"
        verbose_name_plural = "Режимы игры"
        ordering = ["id"]

    def __str__(self):
        return self.name


class Role(models.Model):
    """Игровая роль: мафия, мирный, комиссар и т.д."""
    name = models.CharField("Название роли", max_length=100)
    description = models.TextField("Описание")
    is_unique = models.BooleanField("Уникальная роль", default=False)
    turn_order = models.PositiveIntegerField(
        "Порядок хода",
        null=True,
        blank=True,
        help_text="Чем меньше число, тем раньше ходит роль в ночной фазе",
    )

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Session(models.Model):
    """Игровая сессия (отдельная партия/вечер)."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Запланирована"
        ACTIVE = "active", "Идёт"
        FINISHED = "finished", "Завершена"

    mode = models.ForeignKey(
        Mode,
        verbose_name="Режим",
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    host = models.ForeignKey(
        User,
        verbose_name="Ведущий",
        on_delete=models.PROTECT,
        related_name="hosted_sessions",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    players_count = models.PositiveIntegerField("Количество игроков")
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    finished_at = models.DateTimeField("Завершена", null=True, blank=True)

    class Meta:
        verbose_name = "Игровая сессия"
        verbose_name_plural = "Игровые сессии"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Сессия #{self.id} — {self.mode.name} ({self.get_status_display()})"


class Phase(models.Model):
    """Фазы игры: ночь, день, голосование и т.п."""
    name = models.CharField("Название фазы", max_length=100)
    order = models.PositiveIntegerField(
        "Порядок в круге",
        help_text="1 – ночь, 2 – день, 3 – голосование и т.п.",
    )

    class Meta:
        verbose_name = "Фаза игры"
        verbose_name_plural = "Фазы игры"
        ordering = ["order"]

    def __str__(self):
        return self.name


class Player(models.Model):
    """Конкретный игрок в рамках сессии."""
    class PlayerStatus(models.TextChoices):
        ALIVE = "alive", "В игре"
        DEAD = "dead", "Выбыл"

    session = models.ForeignKey(
        Session,
        verbose_name="Сессия",
        on_delete=models.CASCADE,
        related_name="players",
    )
    name = models.CharField("Имя в партии", max_length=100)
    role = models.ForeignKey(
        Role,
        verbose_name="Роль",
        on_delete=models.PROTECT,
        related_name="players",
    )
    status = models.CharField(
        "Статус игрока",
        max_length=10,
        choices=PlayerStatus.choices,
        default=PlayerStatus.ALIVE,
    )
    seat_number = models.PositiveIntegerField(
        "Номер места за столом",
        null=True,
        blank=True,
    )
    fail_phase = models.ForeignKey(
        Phase,
        verbose_name="Фаза выбывания",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="failed_players",
    )
    notes = models.CharField("Примечания", max_length=300, blank=True)

    class Meta:
        verbose_name = "Игрок"
        verbose_name_plural = "Игроки"
        ordering = ["session", "seat_number", "name"]

    def __str__(self):
        return f"{self.name} (сессия #{self.session_id})"


class Vote(models.Model):
    """Голос одного игрока против другого в конкретной фазе."""
    session = models.ForeignKey(
        Session,
        verbose_name="Сессия",
        on_delete=models.CASCADE,
        related_name="votes",
    )
    phase = models.ForeignKey(
        Phase,
        verbose_name="Фаза",
        on_delete=models.PROTECT,
        related_name="votes",
    )
    round_number = models.PositiveIntegerField(
        "Номер круга",
        help_text="Номер игрового круга/дня",
    )
    voter = models.ForeignKey(
        Player,
        verbose_name="Голосующий",
        on_delete=models.CASCADE,
        related_name="given_votes",
    )
    target = models.ForeignKey(
        Player,
        verbose_name="Цель голосования",
        on_delete=models.CASCADE,
        related_name="received_votes",
    )

    class Meta:
        verbose_name = "Голос"
        verbose_name_plural = "Голоса"
        ordering = ["session", "round_number"]

    def __str__(self):
        return f"Голос {self.voter.name} против {self.target.name} (круг {self.round_number})"


class Result(models.Model):
    """Итоги партии для сессии."""

    class WinnerSide(models.TextChoices):
        MAFIA = "mafia", "Мафия"
        TOWN = "town", "Мирные"

    session = models.OneToOneField(
        Session,
        verbose_name="Сессия",
        on_delete=models.CASCADE,
        related_name="result",
    )
    winner_side = models.CharField(
        "Победившая сторона",
        max_length=10,
        choices=WinnerSide.choices,
    )
    rounds_count = models.PositiveIntegerField("Количество кругов")
    mafia_count = models.PositiveIntegerField("Количество мафии")
    town_count = models.PositiveIntegerField("Количество мирных")

    class Meta:
        verbose_name = "Результат партии"
        verbose_name_plural = "Результаты партий"

    def __str__(self):
        return f"Результат сессии #{self.session_id} ({self.get_winner_side_display()})"
