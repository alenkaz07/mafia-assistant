import random

from django.core.management.base import BaseCommand
from django.conf import settings

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from game.models import Session, Player, Mode

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

User = get_user_model()


class Command(BaseCommand):
    """
    Management-команда: python manage.py runbot

    Телеграм-бот для ведущего мафии.
    Логика:
      - в памяти (self.games) — текущее состояние партий по чатам,
      - в БД (Session / Player) — чтобы сессии и игроки были видны на сайте.
    """

    help = "Запуск Telegram-бота для мафии"

    # Фазы игры
    PHASE_NIGHT = "night"
    PHASE_DAY = "day"
    PHASE_VOTE = "vote"
    PHASE_FINISHED = "finished"

    # Роли
    ROLE_MAFIA = "mafia"
    ROLE_DON = "don"
    ROLE_TOWN = "town"
    ROLE_DETECTIVE = "detective"
    ROLE_DOCTOR = "doctor"

    # Режимы игры
    GAME_MODE_CLASSIC = "classic"
    GAME_MODE_SPORT = "sport"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.games: dict[int, dict] = {}

    # Вспомогательные методы

    def _get_chat_id(self, update: Update):
        """Достаём chat_id из апдейта."""
        if update.effective_chat:
            return update.effective_chat.id
        return None

    def _get_game(self, update: Update):
        """Возвращаем состояние игры для текущего чата (или None)."""
        chat_id = self._get_chat_id(update)
        if chat_id is None:
            return None
        return self.games.get(chat_id)

    async def _ensure_game(self, update: Update):
        """
        Проверяем, что игра для этого чата уже создана.
        Если нет — показываем подсказку и возвращаем None.
        """
        game = self._get_game(update)
        if not game and update.message:
            await update.message.reply_text(
                "В этом чате игра ещё не создана.\n"
                "Сначала запусти команду: /startgame 10"
            )
            return None
        return game

    def _find_player(self, game, name: str):
        """Находим игрока по имени (без учёта регистра)."""
        name_lower = name.strip().lower()
        for p in game["players"]:
            if p["name"].lower() == name_lower:
                return p
        return None

    def _alive_players(self, game):
        """Список живых игроков."""
        return [p for p in game["players"] if p["alive"]]

    def _censor_name(self, name: str) -> str:
        """
        Для цензуры имен.
        """
        if not name:
            return ""
        return name[0] + "•" * max(0, len(name) - 1)

    def _assign_roles_random(self, game):
        """
        Простая логика раздачи ролей.

        Если game["game_mode"] == 'sport' и игроков ровно 10 —
        используем "спортивную" раскладку:
          6 мирных, 2 мафии, 1 дон, 1 комиссар.

        Для остальных случаев — универсальное правило:
          1/3 игроков — мафия (не меньше 2),
          + по одному комиссару и доктору.
        """
        players = game["players"]
        n = len(players)
        indices = list(range(n))
        random.shuffle(indices)

        game_mode = game.get("game_mode") or self.GAME_MODE_CLASSIC

        # по умолчанию все мирные
        roles = [self.ROLE_TOWN] * n

        if game_mode == self.GAME_MODE_SPORT and n == 10:
            mafia_count = 2
            don_count = 1
            detective_count = 1
            doctor_count = 0  # в спортивной мафии доктора нет
        else:
            mafia_count = max(2, n // 3)
            don_count = 0
            detective_count = 1
            doctor_count = 1

        idx = 0

        # раздаём мафию
        for _ in range(mafia_count):
            if idx >= n:
                break
            roles[indices[idx]] = self.ROLE_MAFIA
            idx += 1

        # дон
        for _ in range(don_count):
            if idx >= n:
                break
            roles[indices[idx]] = self.ROLE_DON
            idx += 1

        # комиссар
        for _ in range(detective_count):
            if idx >= n:
                break
            roles[indices[idx]] = self.ROLE_DETECTIVE
            idx += 1

        # доктор (не раздаётся в спорт-режиме)
        for _ in range(doctor_count):
            if idx >= n:
                break
            roles[indices[idx]] = self.ROLE_DOCTOR
            idx += 1

        # записываем роли в игроков
        for i, player in enumerate(players):
            player["role"] = roles[i]

        # помечаем, что роли выданы
        game["roles_assigned"] = True

    def _format_role_ru(self, role: str | None) -> str:
        """Человеческое название роли."""
        if role == self.ROLE_MAFIA:
            return "Мафия"
        if role == self.ROLE_DON:
            return "Дон"
        if role == self.ROLE_DETECTIVE:
            return "Комиссар"
        if role == self.ROLE_DOCTOR:
            return "Доктор"
        if role == self.ROLE_TOWN:
            return "Мирный"
        return "—"

    def _night_instructions_text(self, game) -> str:
        """
        Текст-подсказка для ведущего на ночную фазу.
        Показываем имена ролей.
        Доктор упоминается только если он реально есть в игре.
        """
        round_num = game["round"]
        players = game["players"]

        detectives = [
            p for p in players
            if p["alive"] and p["role"] == self.ROLE_DETECTIVE
        ]
        mafias = [
            p for p in players
            if p["alive"] and p["role"] in (self.ROLE_MAFIA, self.ROLE_DON)
        ]
        doctors = [
            p for p in players
            if p["alive"] and p["role"] == self.ROLE_DOCTOR
        ]

        def names_line(lst):
            return ", ".join(p["name"] for p in lst) or "—"

        text_lines = [
            f"🌙 Ночь, круг {round_num}. Все игроки засыпают.",
            "",
            f"1) Просыпается комиссар: {names_line(detectives)}",
            "   Он выбирает, кого проверить:",
            "   команда: /check Имя или /check и выбрать по кнопке",
            "",
            f"2) Просыпается мафия: {names_line(mafias)}",
            "   Они выбирают жертву:",
            "   команда: /kill Имя (или /kill и выбрать кнопкой)",
        ]

        # Доктор только если он вообще существует (в классике)
        if doctors:
            text_lines += [
                "",
                f"3) Просыпается доктор: {names_line(doctors)}",
                "   Он выбирает, кого лечить:",
                "   команда: /heal Имя или /heal и выбрать по кнопке",
            ]

        text_lines += [
            "",
            "Когда все решения приняты, напиши /next – наступит день.",
        ]
        return "\n".join(text_lines)

    def _control_keyboard(self, game: dict | None):
        """
        Быстрые кнопки внизу экрана.
        Кнопка = уже готовая команда, которая сразу отправляется.
        """
        # Нет активной игры для чата
        if not game:
            keyboard = [
                ["/start", "/help"],
                ["/startgame 10"],
            ]
            return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        # Игра уже завершена
        if game.get("phase") == self.PHASE_FINISHED:
            keyboard = [
                ["/start", "/help"],
                ["/startgame 10"],
            ]
            return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        players_count = len(game["players"])
        planned = game["planned_players"]
        roles_mode = game.get("roles_mode")
        phase = game.get("phase")

        # Ещё набираем игроков, режим ролей ещё не выбран
        if players_count < planned and not roles_mode:
            keyboard = [
                ["/addplayer"],
                ["/players", "/help"],
                ["/reset"],
            ]
        # Игроки уже набраны, но роли ещё не выбраны
        elif players_count == planned and not roles_mode:
            keyboard = [
                ["/assign random", "/assign cards"],
                ["/players"],
                ["/help", "/reset"],
            ]
        else:
            # Роли уже выбраны, игра идёт.
            game_mode = game.get("game_mode") or self.GAME_MODE_CLASSIC

            # Разные кнопки в зависимости от фазы.
            if phase == self.PHASE_NIGHT:
                # НОЧЬ
                if game_mode == self.GAME_MODE_SPORT:
                    # Спортивная мафия — без доктора, /heal не показываем
                    keyboard = [
                        ["/players", "/next"],
                        ["/check", "/kill"],
                        ["/help", "/reset"],
                    ]
                else:
                    # Классика — есть доктор
                    keyboard = [
                        ["/players", "/next"],
                        ["/check", "/kill", "/heal"],
                        ["/help", "/reset"],
                    ]
            elif phase == self.PHASE_DAY:
                # ДЕНЬ: обсуждение, только /next
                keyboard = [
                    ["/players", "/next"],
                    ["/help", "/reset"],
                ]
            elif phase == self.PHASE_VOTE:
                # ГОЛОСОВАНИЕ
                keyboard = [
                    ["/players", "/next"],
                    ["/lynch"],
                    ["/help", "/reset"],
                ]
            else:
                # На всякий случай – общий вариант
                keyboard = [
                    ["/players", "/next"],
                    ["/check", "/kill"],
                    ["/help", "/reset"],
                ]

        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def _check_win_and_build_message(self, game):
        """
        Проверяем условия победы и формируем текст с итогами.
        Работает только в режиме random, когда бот знает роли.

        Возвращает строку с итогами или None, если игра не окончена.
        """
        if not (game.get("roles_mode") == "random" and game.get("roles_assigned")):
            return None

        alive_mafia = 0
        alive_town = 0

        for p in game["players"]:
            if not p["alive"]:
                continue
            # Дон тоже считается мафией
            if p["role"] in (self.ROLE_MAFIA, self.ROLE_DON):
                alive_mafia += 1
            else:
                alive_town += 1

        # все мафии мертвы -> победа мирных
        if alive_mafia == 0 and (alive_town > 0):
            winner = "town"
        # мафий столько же или больше, чем мирных -> победа мафии
        elif alive_mafia > 0 and alive_mafia >= alive_town:
            winner = "mafia"
        else:
            return None

        # помечаем игру как завершённую
        game["phase"] = self.PHASE_FINISHED

        lines: list[str] = []
        if winner == "mafia":
            lines.append("💀 Игра окончена. Победила мафия.")
        else:
            lines.append("🌟 Игра окончена. Победили мирные жители.")
        lines.append("")
        lines.append("Итоги партии:")

        for p in game["players"]:
            role_ru = self._format_role_ru(p["role"])
            status = "в игре" if p["alive"] else "выбыл"
            lines.append(f" - {p['name']}: {role_ru}, {status}")

        lines.append("")
        lines.append(
            "Чтобы начать новую партию, запусти /startgame 10 "
            "(или другое число игроков)."
        )
        return "\n".join(lines)

    async def _handle_players_input(self, game: dict, raw_text: str, update: Update):
        """
        Разбор произвольного текста с именами игроков и добавление их в игру.
        Можно через запятую, с новой строки или всё вместе.
        """
        if not update.message:
            return

        if game.get("phase") == self.PHASE_FINISHED:
            await update.message.reply_text(
                "Игра уже завершена. Запусти /startgame N, чтобы начать новую.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if game.get("roles_mode"):
            await update.message.reply_text(
                "Роли уже выбраны, добавить новых игроков нельзя.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # Если уже всё набрали — сразу выходим
        if len(game["players"]) >= game["planned_players"]:
            game["adding_players"] = False
            await update.message.reply_text(
                "Уже добавлено запланированное количество игроков.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # Приводим к формату "имена через запятую"
        normalized = raw_text.replace("\n", ",")
        names = [name.strip() for name in normalized.split(",") if name.strip()]

        if not names:
            await update.message.reply_text(
                "Не нашлись имена в этом сообщении. Напиши игроков через запятую "
                "или с новой строки.",
                reply_markup=self._control_keyboard(game),
            )
            return

        added: list[str] = []
        skipped_existing: list[str] = []
        skipped_full = False

        # Session для создания Player'ов
        session_id = game.get("db_session_id")
        session = None
        if session_id:
            try:
                session = await sync_to_async(Session.objects.get)(id=session_id)
            except Exception as e:
                self.stderr.write(
                    self.style.WARNING(f"Не удалось получить Session из БД: {e}")
                )

        for name in names:
            # Проверка на лимит игроков
            if len(game["players"]) >= game["planned_players"]:
                skipped_full = True
                break

            # Проверка на дубликат
            if self._find_player(game, name):
                skipped_existing.append(name)
                continue

            # Добавляем во внутреннее состояние
            game["players"].append(
                {"name": name, "role": None, "alive": True}
            )
            added.append(name)

            # Добавляем в БД, если есть Session
            if session:
                try:
                    await sync_to_async(Player.objects.create)(
                        session=session,
                        name=name,
                        status=Player.PlayerStatus.ALIVE,
                    )
                except Exception as e:
                    self.stderr.write(
                        self.style.WARNING(f"Не удалось создать Player в БД: {e}")
                    )

        total = len(game["players"])
        planned = game["planned_players"]

        lines: list[str] = []

        if added:
            if len(added) == 1:
                lines.append(f"Добавлен игрок: {added[0]}")
            else:
                lines.append("Добавлены игроки: " + ", ".join(added))
            lines.append(f"Всего добавлено: {total} из {planned}.")
        else:
            lines.append("Новых игроков не добавлено.")

        if skipped_existing:
            lines.append(
                "Пропущены (уже есть в списке): " + ", ".join(skipped_existing)
            )
        if skipped_full:
            lines.append(
                "Достигнуто запланированное количество игроков. "
                "Лишние имена проигнорированы."
            )

        if total == planned:
            lines.append(
                "\nВсе игроки добавлены 🎉\n"
                "Теперь выбери способ раздачи ролей:\n"
                "  /assign random — роли выдаёт бот\n"
                "  /assign cards — роли уже выданы по карточкам, бот их не знает."
            )
            # выключаем режим добора
            game["adding_players"] = False

        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=self._control_keyboard(game),
        )

    # Команды

    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start — приветственное сообщение и краткая инструкция.
        """
        text = (
            "Привет! Я бот-ассистент для ведущего игры в мафию.\n\n"
            "Базовый сценарий:\n"
            " 1️⃣ /startgame 10 — создать игру и указать число игроков\n"
            "     Можно указать режим: /startgame 10 classic или /startgame 10 sport.\n"
            " 2️⃣ /addplayer — включить режим добавления игроков, затем просто присылай имена\n"
            " 3️⃣ /assign random — выдать роли (или /assign cards, если роли по карточкам)\n"
            " 4️⃣ /players — посмотреть список игроков\n"
            " 5️⃣ /next — переключать фазы (Ночь → День → Голосование → Ночь)\n"
            "\n"
            "Внутри ночи:\n"
            "  /check — выбрать игрока для проверки кнопкой\n"
            "  /kill — выбрать жертву мафии кнопками\n"
            "  /kill Имя — выбрать жертву по имени\n"
            "  /heal — выбрать, кого лечит доктор, кнопкой (только в классике)\n"
            "  /heal Имя — выбор лечения доктора по имени\n"
            "На голосовании:\n"
            "  /lynch — исключить игрока по кнопке\n"
            "  /lynch Имя — исключить игрока по имени\n"
        )
        if update.message:
            game = self._get_game(update)
            await update.message.reply_text(
                text,
                reply_markup=self._control_keyboard(game),
            )

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /help — подробный список команд.
        """
        text = (
            "Команды бота:\n"
            " /start — краткая инструкция\n"
            " /help — список команд\n"
            "\n"
            "Создание игры:\n"
            " /startgame N [classic|sport] — создать игру и задать количество игроков\n"
            "    Примеры: /startgame 10 sport, /startgame 8\n"
            " /addplayer — включить режим добавления игроков.\n"
            "    Затем отправляй имена игроков списком (через запятую или с новой строки)\n"
            "    или по одному именем в каждом сообщении.\n"
            " /players — список всех игроков\n"
            " /assign random — раздать роли случайно\n"
            " /assign cards — роли по карточкам (бот их не знает)\n"
            "\n"
            "Ход игры:\n"
            " /next — переход по фазам (Ночь → День → Голосование → следующая Ночь)\n"
            "\n"
            "Ночь:\n"
            " /check — выбрать игрока для проверки кнопкой\n"
            " /check Имя — проверить конкретного игрока\n"
            " /kill — выбрать жертву мафии кнопками\n"
            " /kill Имя — жертва по имени\n"
            " /heal — выбрать, кого лечит доктор, кнопкой (только в классике)\n"
            " /heal Имя — лечение по имени\n"
            "\n"
            "Голосование:\n"
            " /lynch — выбрать, кого исключить, кнопкой\n"
            " /lynch Имя — исключить игрока по имени\n"
            "\n"
            "Сброс текущей партии:\n"
            " /reset — сбросить игру в этом чате и пометить сессию как сброшенную.\n"
            "\n"
            "Автор: Казарина Алёна Алексеевна\n"
        )
        if update.message:
            game = self._get_game(update)
            await update.message.reply_text(
                text,
                reply_markup=self._control_keyboard(game),
            )

    async def startgame_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /startgame N [classic|sport] — создать новую игру в чате.

        Здесь:
        - создаём/обновляем состояние в self.games[chat_id];
        - создаём Session в БД, чтобы её было видно на сайте.
        """
        chat_id = self._get_chat_id(update)
        if chat_id is None or not update.message:
            return

        # читаем аргументы: число игроков и (опционально) режим
        planned = 10
        game_mode = self.GAME_MODE_CLASSIC  # по умолчанию

        args = context.args or []

        if len(args) >= 1:
            try:
                planned = int(args[0])
            except ValueError:
                await update.message.reply_text(
                    "Нужно указать количество игроков числом.\n\n"
                    "Пример: /startgame 10\n"
                    "или: /startgame 10 sport",
                    reply_markup=self._control_keyboard(self._get_game(update)),
                )
                return

        # если режим явно указан вторым аргументом
        if len(args) >= 2:
            mode_raw = args[1].lower()
            if mode_raw in ("classic", "классика", "классическая"):
                game_mode = self.GAME_MODE_CLASSIC
            elif mode_raw in ("sport", "спорт", "спортивная"):
                game_mode = self.GAME_MODE_SPORT
            else:
                await update.message.reply_text(
                    "Неизвестный режим.\n"
                    "Используй classic или sport.\n"
                    "Например: /startgame 10 classic",
                    reply_markup=self._control_keyboard(self._get_game(update)),
                )
                return
        else:
            # если режим не указан, выберем по количеству:
            #   10 игроков - спортивная,
            #   иначе — классическая
            if planned == 10:
                game_mode = self.GAME_MODE_SPORT
            else:
                game_mode = self.GAME_MODE_CLASSIC

        if planned < 6:
            await update.message.reply_text(
                "Минимум игроков — 6. Попробуй ещё раз.\n"
                "Например: /startgame 10",
                reply_markup=self._control_keyboard(self._get_game(update)),
            )
            return

        # Запись Session в БД
        db_session_id = None
        extra_line = ""
        try:
            host_id = getattr(settings, "TG_BOT_HOST_USER_ID", None)
            if host_id is not None:
                host_user = await sync_to_async(User.objects.get)(id=host_id)

                sport_mode_id = getattr(settings, "TG_BOT_MODE_SPORT_ID", None)
                classic_mode_id = getattr(settings, "TG_BOT_MODE_CLASSIC_ID", None)

                mode_obj = None

                if game_mode == self.GAME_MODE_SPORT and sport_mode_id:
                    mode_obj = await sync_to_async(Mode.objects.get)(id=sport_mode_id)
                elif game_mode == self.GAME_MODE_CLASSIC and classic_mode_id:
                    mode_obj = await sync_to_async(Mode.objects.get)(
                        id=classic_mode_id
                    )

                if mode_obj is None:
                    # запасной вариант: берём первый попавшийся режим
                    mode_obj = await sync_to_async(Mode.objects.first)()

                if mode_obj and host_user:
                    session = await sync_to_async(Session.objects.create)(
                        mode=mode_obj,
                        host=host_user,
                        status=Session.Status.PLANNED,
                        players_count=planned,
                    )
                    db_session_id = session.id
                    extra_line = f"Эта партия сохранена как сессия #{session.id} на сайте.\n"
        except Exception as e:
            # Не падаем, просто пишем предупреждение в консоль
            self.stderr.write(
                self.style.WARNING(f"Не удалось создать Session в БД: {e}")
            )

        mode_human = (
            "классическая мафия"
            if game_mode == self.GAME_MODE_CLASSIC
            else "спортивная мафия"
        )

        # Запоминаем состояние игры в памяти
        game = {
            "planned_players": planned,
            "players": [],
            "roles_assigned": False,
            "roles_mode": None,  # 'random' или 'cards'
            "phase": None,       # night/day/vote/finished
            "round": 0,
            "pending_kill": None,
            "pending_heal": None,
            "pending_check": None,
            "last_night_killed": None,
            "db_session_id": db_session_id,
            "game_mode": game_mode,
            "adding_players": False,
        }
        self.games[chat_id] = game

        await update.message.reply_text(
            f"Создана новая игра в этом чате.\n"
            f"Запланировано игроков: {planned}.\n"
            f"Режим: {mode_human}.\n"
            f"{extra_line}"
            "Теперь добавь игроков.\n"
            "1) Введи команду /addplayer\n"
            "2) Отправь имена игроков списком (через запятую или с новой строки)\n"
            "   или по одному именем в каждом сообщении.",
            reply_markup=self._control_keyboard(game),
        )

    async def addplayer_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /addplayer — включить режим добавления игроков.
        После этой команды можно просто отправлять сообщения с именами игроков
        (через запятую, с новой строки или по одному).
        Также можно использовать /addplayer Имя1, Имя2, Имя3 — будет разбор как списка.
        """
        game = await self._ensure_game(update)
        if not game or not update.message:
            return

        if game.get("phase") == self.PHASE_FINISHED:
            await update.message.reply_text(
                "Игра уже завершена. Запусти /startgame N, чтобы начать новую.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if game.get("roles_mode"):
            await update.message.reply_text(
                "Роли уже выбраны, добавить новых игроков нельзя.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if len(game["players"]) >= game["planned_players"]:
            await update.message.reply_text(
                "Уже добавлено запланированное количество игроков.\n"
                "Если нужно начать заново, используй /startgame N.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # Если в команде есть аргументы — обрабатываем их как список имён сразу
        if context.args:
            raw = " ".join(context.args)
            await self._handle_players_input(game, raw, update)
            return

        # Иначе включаем режим добавления игроков
        game["adding_players"] = True
        remaining = game["planned_players"] - len(game["players"])

        await update.message.reply_text(
            "Режим добавления игроков включён.\n"
            "Теперь отправляй имена игроков:\n"
            " • списком через запятую:  Аня, Ваня, Петя\n"
            " • или с новой строки:\n"
            "      Аня\n"
            "      Ваня\n"
            "      Петя\n"
            " • или по одному именем в каждом новом сообщении.\n"
            f"Нужно добавить ещё примерно {remaining} игрок(ов).",
            reply_markup=self._control_keyboard(game),
        )

    async def players_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /players — показать список игроков.
        Если роли уже выданы (random), покажем и роли.
        """
        game = await self._ensure_game(update)
        if not game or not update.message:
            return

        players = game["players"]
        if not players:
            await update.message.reply_text(
                "Пока игроков нет. Добавь их: /addplayer",
                reply_markup=self._control_keyboard(game),
            )
            return

        show_roles = game.get("roles_assigned", False)
        lines = []
        for idx, p in enumerate(players, start=1):
            status = "в игре" if p["alive"] else "выбыл"
            if show_roles:
                role_ru = self._format_role_ru(p["role"])
                lines.append(f"{idx}. {p['name']} — {role_ru}, {status}")
            else:
                lines.append(f"{idx}. {p['name']} — {status}")

        await update.message.reply_text(
            "Игроки:\n" + "\n".join(lines),
            reply_markup=self._control_keyboard(game),
        )

    async def assign_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /assign random/cards — выбор способа выдачи ролей.
        """
        game = await self._ensure_game(update)
        if not game or not update.message:
            return

        if game.get("phase") == self.PHASE_FINISHED:
            await update.message.reply_text(
                "Игра уже завершена. Запусти /startgame N, чтобы начать новую.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if len(game["players"]) != game["planned_players"]:
            await update.message.reply_text(
                "Сначала добавь всех запланированных игроков.\n"
                "Потом можно выдавать роли.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if not context.args:
            await update.message.reply_text(
                "Укажи режим: random или cards.\n\n"
                "Примеры:\n"
                "  /assign random\n"
                "  /assign cards",
                reply_markup=self._control_keyboard(game),
            )
            return

        mode = context.args[0].lower()
        if mode not in ("random", "cards"):
            await update.message.reply_text(
                "Неизвестный режим. Используй:\n"
                "  /assign random  — роли раздаёт бот\n"
                "  /assign cards   — роли выданы по карточкам (бот их не знает)",
            )
            return

        game["roles_mode"] = mode

        # Обновить статус Session в БД (перевести в ACTIVE)
        session_id = game.get("db_session_id")
        if session_id:
            try:
                session = await sync_to_async(Session.objects.get)(id=session_id)
                session.status = Session.Status.ACTIVE
                await sync_to_async(session.save)()
            except Exception as e:
                self.stderr.write(
                    self.style.WARNING(f"Не удалось обновить статус Session: {e}")
                )

        if mode == "random":
            # раздаём роли и начинаем первую ночь
            self._assign_roles_random(game)
            game["phase"] = self.PHASE_NIGHT
            game["round"] = 1

            # показываем ведущему роли
            lines = ["Роли выданы случайно (НЕ показывай этот список игрокам):", ""]
            for p in game["players"]:
                role_ru = self._format_role_ru(p["role"])
                lines.append(f" - {p['name']}: {role_ru}")

            lines.append("")
            lines.append("Игра начинается с ночи.")

            # 1) список ролей
            await update.message.reply_text(
                "\n".join(lines),
                reply_markup=self._control_keyboard(game),
            )

            # 2) сразу даём подробные подсказки для НОЧИ (круг 1)
            await update.message.reply_text(
                self._night_instructions_text(game),
                reply_markup=self._control_keyboard(game),
            )

        else:  # cards
            # В режиме "карточки" бот не знает ролей, но всё равно ведёт фазы.
            game["roles_assigned"] = False
            game["phase"] = self.PHASE_NIGHT
            game["round"] = 1

            await update.message.reply_text(
                "Режим «карточки»: роли уже выданы офлайн, бот их не знает.\n"
                "Игра начинается с ночи.\n\n"
                "Для подсказок ночью напиши: /next",
                reply_markup=self._control_keyboard(game),
            )

    async def check_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /check [Имя] — проверка комиссаром.
        Работает только ночью и только если роли раздавали random.

        Варианты:
        - /check       — показать кнопки с живыми игроками;
        - /check Имя   — проверить конкретного игрока по имени.
        """
        game = await self._ensure_game(update)
        if not game or not update.message:
            return

        if game.get("phase") == self.PHASE_FINISHED:
            await update.message.reply_text(
                "Игра уже завершена. Запусти /startgame N, чтобы начать новую.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if game["phase"] != self.PHASE_NIGHT:
            await update.message.reply_text(
                "Проверять можно только ночью.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if not game.get("roles_mode") == "random" or not game.get("roles_assigned"):
            await update.message.reply_text(
                "В режиме карточек бот не знает ролей игроков.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # если имя не указано — показываем кнопки
        if not context.args:
            alive = self._alive_players(game)
            if not alive:
                await update.message.reply_text(
                    "Нет живых игроков для проверки.",
                    reply_markup=self._control_keyboard(game),
                )
                return

            keyboard = [
                [
                    InlineKeyboardButton(
                        p["name"],
                        callback_data=f"check:{idx}",
                    )
                ]
                for idx, p in enumerate(game["players"])
                if p["alive"]
            ]
            markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Кого проверяет комиссар?",
                reply_markup=markup,
            )
            return

        # /check Имя
        name = " ".join(context.args).strip()
        player = self._find_player(game, name)
        if not player:
            await update.message.reply_text(
                f"Игрок «{name}» не найден.",
                reply_markup=self._control_keyboard(game),
            )
            return

        role_ru = self._format_role_ru(player["role"])
        game["pending_check"] = player["name"]

        await update.message.reply_text(
            f"Комиссар проверяет игрока: {player['name']}.\n"
            f"Роль этого игрока: {role_ru}.",
            reply_markup=self._control_keyboard(game),
        )

    async def kill_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /kill [Имя] — выбор жертвы мафии.

        Варианты:
        - /kill       — показать кнопки со списком живых игроков;
        - /kill Имя   — указать жертву текстом.
        """
        game = await self._ensure_game(update)
        if not game or not update.message:
            return

        if game.get("phase") == self.PHASE_FINISHED:
            await update.message.reply_text(
                "Игра уже завершена. Запусти /startgame N, чтобы начать новую.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if game["phase"] != self.PHASE_NIGHT:
            await update.message.reply_text(
                "Жертву мафии можно выбирать только ночью.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # Если имя не указано — показать кнопки с живыми игроками
        if not context.args:
            alive = self._alive_players(game)
            if not alive:
                await update.message.reply_text(
                    "Все игроки уже выбыли 🙂",
                    reply_markup=self._control_keyboard(game),
                )
                return

            keyboard = [
                [
                    InlineKeyboardButton(
                        p["name"],
                        callback_data=f"kill:{idx}",
                    )
                ]
                for idx, p in enumerate(game["players"])
                if p["alive"]
            ]
            markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Выбери жертву мафии:",
                reply_markup=markup,
            )
            return

        # Вариант: /kill Имя
        name = " ".join(context.args).strip()
        player = self._find_player(game, name)
        if not player:
            await update.message.reply_text(
                f"Игрок «{name}» не найден.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if not player["alive"]:
            await update.message.reply_text(
                f"Игрок «{player['name']}» уже выбыл.",
                reply_markup=self._control_keyboard(game),
            )
            return

        game["pending_kill"] = player["name"]

        await update.message.reply_text(
            f"Мафия выбрала жертву: {player['name']}.\n"
            "Если нужно изменить выбор — просто вызови /kill ещё раз с другим именем "
            "или выбери другого игрока через кнопки.",
            reply_markup=self._control_keyboard(game),
        )

    async def heal_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /heal [Имя] — выбор лечения доктора.

        Варианты:
        - /heal       — показать кнопки с живыми игроками;
        - /heal Имя   — указать, кого лечит доктор.
        """
        game = await self._ensure_game(update)
        if not game or not update.message:
            return

        # В спортивной мафии доктора нет
        game_mode = game.get("game_mode") or self.GAME_MODE_CLASSIC
        if game_mode == self.GAME_MODE_SPORT:
            await update.message.reply_text(
                "В спортивной мафии доктор не используется, команда /heal недоступна.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if game.get("phase") == self.PHASE_FINISHED:
            await update.message.reply_text(
                "Игра уже завершена. Запусти /startgame N, чтобы начать новую.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if game["phase"] != self.PHASE_NIGHT:
            await update.message.reply_text(
                "Доктор лечит только ночью.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # нет аргумента — показываем кнопки
        if not context.args:
            alive = self._alive_players(game)
            if not alive:
                await update.message.reply_text(
                    "Нет живых игроков для лечения.",
                    reply_markup=self._control_keyboard(game),
                )
                return

            keyboard = [
                [
                    InlineKeyboardButton(
                        p["name"],
                        callback_data=f"heal:{idx}",
                    )
                ]
                for idx, p in enumerate(game["players"])
                if p["alive"]
            ]
            markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Кого лечит доктор?",
                reply_markup=markup,
            )
            return

        name = " ".join(context.args).strip()
        player = self._find_player(game, name)
        if not player:
            await update.message.reply_text(
                f"Игрок «{name}» не найден.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if not player["alive"]:
            await update.message.reply_text(
                f"Игрок «{player['name']}» уже выбыл.",
                reply_markup=self._control_keyboard(game),
            )
            return

        game["pending_heal"] = player["name"]

        await update.message.reply_text(
            f"Доктор будет лечить игрока: {player['name']}.\n"
            "Если нужно изменить выбор — вызови /heal ещё раз.",
            reply_markup=self._control_keyboard(game),
        )

    async def lynch_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /lynch [Имя] — исключить игрока по результатам голосования.

        Варианты:
        - /lynch       — показать кнопки с живыми игроками;
        - /lynch Имя   — исключить игрока по имени.
        """
        game = await self._ensure_game(update)
        if not game or not update.message:
            return

        if game.get("phase") == self.PHASE_FINISHED:
            await update.message.reply_text(
                "Игра уже завершена. Запусти /startgame N, чтобы начать новую.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if game["phase"] != self.PHASE_VOTE:
            await update.message.reply_text(
                "Исключать игрока голосованием можно только на стадии голосования.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # Нет имени — показываем кнопки
        if not context.args:
            alive = self._alive_players(game)
            if not alive:
                await update.message.reply_text(
                    "Все уже выбыли из игры 🙂",
                    reply_markup=self._control_keyboard(game),
                )
                return

            keyboard = [
                [
                    InlineKeyboardButton(
                        p["name"],
                        callback_data=f"lynch:{idx}",
                    )
                ]
                for idx, p in enumerate(game["players"])
                if p["alive"]
            ]
            markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Кого исключают по итогам голосования?",
                reply_markup=markup,
            )
            return

        name = " ".join(context.args).strip()
        player = self._find_player(game, name)
        if not player:
            await update.message.reply_text(
                f"Игрок «{name}» не найден.",
                reply_markup=self._control_keyboard(game),
            )
            return

        if not player["alive"]:
            await update.message.reply_text(
                f"Игрок «{player['name']}» уже выбыл.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # помечаем игрока "выбыл"
        player["alive"] = False

        # обновляем статус игрока в БД
        session_id = game.get("db_session_id")
        if session_id:
            try:
                await sync_to_async(
                    Player.objects.filter(
                        session_id=session_id,
                        name=player["name"],
                    ).update
                )(status=Player.PlayerStatus.DEAD)
            except Exception as e:
                self.stderr.write(
                    self.style.WARNING(f"Не удалось обновить Player в БД: {e}")
                )

        await update.message.reply_text(
            f"По итогам голосования из игры выбывает: {player['name']}.",
            reply_markup=self._control_keyboard(game),
        )

        # Проверяем победу после голосования
        win_text = self._check_win_and_build_message(game)
        if win_text and update.message:
            # если игра закончилась — пометим Session в БД как завершённую
            session_id = game.get("db_session_id")
            if session_id:
                try:
                    session = await sync_to_async(Session.objects.get)(id=session_id)
                    session.status = Session.Status.FINISHED
                    await sync_to_async(session.save)()
                except Exception as e:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Не удалось пометить Session как завершённую: {e}"
                        )
                    )

            await update.message.reply_text(
                win_text,
                reply_markup=self._control_keyboard(game),
            )

    async def next_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /next — переключение фаз:
        Ночь → День → Голосование → Ночь → ...
        """
        game = await self._ensure_game(update)
        if not game or not update.message:
            return

        if game.get("phase") == self.PHASE_FINISHED:
            await update.message.reply_text(
                "Игра уже завершена. Запусти /startgame N, чтобы начать новую.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # если игра только что настроена — запускаем первую ночь
        if game["phase"] is None:
            game["phase"] = self.PHASE_NIGHT
            game["round"] = 1
            await update.message.reply_text(
                self._night_instructions_text(game),
                reply_markup=self._control_keyboard(game),
            )
            return

        phase = game["phase"]

        # Переход: НОЧЬ -> ДЕНЬ
        if phase == self.PHASE_NIGHT:
            kill_name = game["pending_kill"]
            heal_name = game["pending_heal"]

            killed_player_name = None

            if kill_name and heal_name and kill_name == heal_name:
                # доктор вылечил жертву
                game["last_night_killed"] = None
                killed_msg = "Доктор успел вылечить жертву. Ночью никто не убит."
            elif kill_name:
                player = self._find_player(game, kill_name)
                if player and player["alive"]:
                    player["alive"] = False
                    killed_player_name = player["name"]
                    game["last_night_killed"] = killed_player_name
                    killed_msg = f"Ночью убит игрок: {killed_player_name}."
                else:
                    game["last_night_killed"] = None
                    killed_msg = (
                        "Жертва мафии не найдена (возможно, игрок уже выбыл)."
                    )
            else:
                game["last_night_killed"] = None
                killed_msg = "Мафия никого не выбрала, ночью никто не убит."

            # Если кто-то погиб — синхронизируем в БД
            session_id = game.get("db_session_id")
            if killed_player_name and session_id:
                try:
                    await sync_to_async(
                        Player.objects.filter(
                            session_id=session_id,
                            name=killed_player_name,
                        ).update
                    )(status=Player.PlayerStatus.DEAD)
                except Exception as e:
                    self.stderr.write(
                        self.style.WARNING(f"Не удалось обновить Player в БД: {e}")
                    )

            # очистить ночные выборы
            game["pending_kill"] = None
            game["pending_heal"] = None
            game["pending_check"] = None

            game["phase"] = self.PHASE_DAY

            day_round = game.get("round", 1)

            await update.message.reply_text(
                f"🌞 День, круг {day_round}.\n"
                f"{killed_msg}\n\n"
                "Ведущий объявляет результаты ночи и даёт время на обсуждение.\n"
                "Когда обсуждение закончится — напиши /next, начнётся голосование.",
                reply_markup=self._control_keyboard(game),
            )

            # Проверяем победу после ночи
            win_text = self._check_win_and_build_message(game)
            if win_text and update.message:
                # если игра закончилась — пометим Session в БД как завершённую
                session_id = game.get("db_session_id")
                if session_id:
                    try:
                        session = await sync_to_async(Session.objects.get)(
                            id=session_id
                        )
                        session.status = Session.Status.FINISHED
                        await sync_to_async(session.save)()
                    except Exception as e:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Не удалось пометить Session как завершённую: {e}"
                            )
                        )

                await update.message.reply_text(
                    win_text,
                    reply_markup=self._control_keyboard(game),
                )
            return

        # Переход: ДЕНЬ -> ГОЛОСОВАНИЕ
        if phase == self.PHASE_DAY:
            game["phase"] = self.PHASE_VOTE

            await update.message.reply_text(
                f"🗳 Голосование, круг {game['round']}.\n\n"
                "1) Объяви кандидатов.\n"
                "2) Собери голоса.\n"
                "3) Исключи игрока командой:\n"
                "   /lynch Имя\n\n"
                "Или используй /lynch и выбери игрока по кнопке.\n"
                "После того как игрок исключён, напиши /next, "
                "чтобы перейти к следующей ночи.",
                reply_markup=self._control_keyboard(game),
            )
            return

        # Переход: ГОЛОСОВАНИЕ -> НОЧЬ (следующий круг)
        if phase == self.PHASE_VOTE:
            game["round"] += 1
            game["phase"] = self.PHASE_NIGHT
            await update.message.reply_text(
                self._night_instructions_text(game),
                reply_markup=self._control_keyboard(game),
            )
            return

        # На всякий случай
        await update.message.reply_text(
            "Что-то пошло не так с фазой игры. "
            "Попробуй /startgame N, чтобы начать заново.",
            reply_markup=self._control_keyboard(game),
        )

    async def reset_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /reset — сбросить текущую партию в этом чате.

        Что делаем:
        - помечаем связанную Session в БД как 'сброшена'
        - удаляем состояние игры из self.games[chat_id].
        """
        chat_id = self._get_chat_id(update)
        if chat_id is None or not update.message:
            return

        game = self.games.get(chat_id)
        if not game:
            await update.message.reply_text(
                "Для этого чата игра ещё не создана. "
                "Сначала запусти /startgame N.",
                reply_markup=self._control_keyboard(None),
            )
            return

        session_id = game.get("db_session_id")

        if session_id:
            try:
                session = await sync_to_async(Session.objects.get)(id=session_id)
                # Статус CANCELLED.
                status_cancel = getattr(
                    Session.Status,
                    "CANCELLED",
                    Session.Status.FINISHED,
                )
                session.status = status_cancel
                await sync_to_async(session.save)()
            except Exception as e:
                self.stderr.write(
                    self.style.WARNING(
                        f"Не удалось пометить Session как сброшенную: {e}"
                    )
                )

        # Удаляем состояние партии из памяти
        self.games.pop(chat_id, None)

        await update.message.reply_text(
            "Текущая партия сброшена.\n"
            "Можно начать новую командой /startgame 10.",
            reply_markup=self._control_keyboard(None),
        )

    # Обработка обычных текстовых сообщений (для добавления игроков)

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработка обычных текстовых сообщений (без команды).
        Используется для добавления игроков после /addplayer.
        """
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        if not text:
            return

        # На всякий случай игнорируем команды (MessageHandler уже фильтрует)
        if text.startswith("/"):
            return

        game = self._get_game(update)
        if not game:
            return

        # Если игра уже идёт или роли выбраны — не воспринимаем текст как имена
        if game.get("roles_mode"):
            return

        # Если режим добавления игроков не включён — тоже игнорируем
        if not game.get("adding_players"):
            return

        await self._handle_players_input(game, text, update)

    # Обработчик нажатий на inline-кнопки

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработка нажатий на inline-кнопки:
        - kill:ID   — выбор жертвы мафии;
        - check:ID  — выбор проверки комиссара;
        - heal:ID   — выбор лечения доктора;
        - lynch:ID  — выбор исключаемого игрока на голосовании.
        """
        query = update.callback_query
        if not query:
            return

        await query.answer()

        data = query.data or ""
        chat_id = self._get_chat_id(update)
        if chat_id is None:
            return

        game = self.games.get(chat_id)
        if not game:
            await query.edit_message_text(
                "Игра для этого чата не найдена. "
                "Запусти /startgame N."
            )
            return

        # ---- Выбор жертвы мафии ----
        if data.startswith("kill:"):
            if game.get("phase") != self.PHASE_NIGHT:
                await query.edit_message_text(
                    "Жертву мафии можно выбирать только ночью."
                )
                return

            try:
                idx = int(data.split(":", 1)[1])
            except (ValueError, IndexError):
                return

            try:
                player = game["players"][idx]
            except IndexError:
                await query.edit_message_text("Игрок не найден.")
                return

            if not player["alive"]:
                await query.edit_message_text(
                    f"Игрок «{player['name']}» уже выбыл."
                )
                return

            game["pending_kill"] = player["name"]

            await query.edit_message_text(
                f"Мафия выбрала жертву: {player['name']}.\n"
                "Если нужно изменить выбор — снова вызови /kill "
                "и выбери другого игрока."
            )
            return

        # Выбор проверки комиссара
        if data.startswith("check:"):
            if game.get("phase") != self.PHASE_NIGHT:
                await query.edit_message_text(
                    "Проверять можно только ночью."
                )
                return

            if not game.get("roles_mode") == "random" or not game.get("roles_assigned"):
                await query.edit_message_text(
                    "В режиме карточек бот не знает ролей игроков."
                )
                return

            try:
                idx = int(data.split(":", 1)[1])
            except (ValueError, IndexError):
                return

            try:
                player = game["players"][idx]
            except IndexError:
                await query.edit_message_text("Игрок не найден.")
                return

            if not player["alive"]:
                await query.edit_message_text(
                    f"Игрок «{player['name']}» уже выбыл."
                )
                return

            game["pending_check"] = player["name"]
            role_ru = self._format_role_ru(player["role"])

            await query.edit_message_text(
                f"Комиссар проверяет игрока: {player['name']}.\n"
                f"Роль этого игрока: {role_ru}."
            )
            return

        # Выбор лечения доктора
        if data.startswith("heal:"):
            # На всякий случай: если спортивная мафия — игнорируем
            game_mode = game.get("game_mode") or self.GAME_MODE_CLASSIC
            if game_mode == self.GAME_MODE_SPORT:
                await query.edit_message_text(
                    "В спортивной мафии доктор не используется."
                )
                return

            if game.get("phase") != self.PHASE_NIGHT:
                await query.edit_message_text(
                    "Доктор лечит только ночью."
                )
                return

            try:
                idx = int(data.split(":", 1)[1])
            except (ValueError, IndexError):
                return

            try:
                player = game["players"][idx]
            except IndexError:
                await query.edit_message_text("Игрок не найден.")
                return

            if not player["alive"]:
                await query.edit_message_text(
                    f"Игрок «{player['name']}» уже выбыл."
                )
                return

            game["pending_heal"] = player["name"]

            await query.edit_message_text(
                f"Доктор будет лечить игрока: {player['name']}.\n"
                "Если нужно изменить выбор — снова вызови /heal "
                "и выбери другого игрока."
            )
            return

        # Исключение на голосовании
        if data.startswith("lynch:"):
            if game.get("phase") != self.PHASE_VOTE:
                await query.edit_message_text(
                    "Исключать игрока голосованием можно только на стадии голосования."
                )
                return

            try:
                idx = int(data.split(":", 1)[1])
            except (ValueError, IndexError):
                return

            try:
                player = game["players"][idx]
            except IndexError:
                await query.edit_message_text("Игрок не найден.")
                return

            if not player["alive"]:
                await query.edit_message_text(
                    f"Игрок «{player['name']}» уже выбыл."
                )
                return

            # помечаем игрока "выбыл"
            player["alive"] = False

            # обновляем статус игрока в БД
            session_id = game.get("db_session_id")
            if session_id:
                try:
                    await sync_to_async(
                        Player.objects.filter(
                            session_id=session_id,
                            name=player["name"],
                        ).update
                    )(status=Player.PlayerStatus.DEAD)
                except Exception as e:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Не удалось обновить Player в БД: {e}"
                        )
                    )

            # сообщение вместо инлайн-кнопок
            await query.edit_message_text(
                f"По итогам голосования из игры выбывает: {player['name']}."
            )

            # Проверяем победу
            win_text = self._check_win_and_build_message(game)
            if win_text:
                if session_id:
                    try:
                        session = await sync_to_async(Session.objects.get)(
                            id=session_id
                        )
                        session.status = Session.Status.FINISHED
                        await sync_to_async(session.save)()
                    except Exception as e:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Не удалось пометить Session как завершённую: {e}"
                            )
                        )

                # отдельным сообщением — итоги и клавиатура
                await query.message.reply_text(
                    win_text,
                    reply_markup=self._control_keyboard(game),
                )
            return

    # Запуск бота

    def handle(self, *args, **options):
        """
        Точка входа management-команды.
        Запускает приложение python-telegram-bot и регистрирует обработчики команд.
        """
        token = getattr(settings, "TG_BOT_TOKEN", None)
        if not token:
            self.stderr.write(
                self.style.ERROR(
                    "В settings.py не найден TG_BOT_TOKEN."
                )
            )
            return

        app = ApplicationBuilder().token(token).build()

        # Команды
        app.add_handler(CommandHandler("start", self.start_cmd))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("startgame", self.startgame_cmd))
        app.add_handler(CommandHandler("addplayer", self.addplayer_cmd))
        app.add_handler(CommandHandler("players", self.players_cmd))
        app.add_handler(CommandHandler("assign", self.assign_cmd))
        app.add_handler(CommandHandler("check", self.check_cmd))
        app.add_handler(CommandHandler("kill", self.kill_cmd))
        app.add_handler(CommandHandler("heal", self.heal_cmd))
        app.add_handler(CommandHandler("lynch", self.lynch_cmd))
        app.add_handler(CommandHandler("next", self.next_cmd))
        app.add_handler(CommandHandler("reset", self.reset_cmd))

        # Обработка обычных текстовых сообщений (имена игроков после /addplayer)
        app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.text_message,
            )
        )

        # Обработка inline-кнопок
        app.add_handler(CallbackQueryHandler(self.button_callback))

        self.stdout.write(
            self.style.SUCCESS("Бот запущен. Нажми Ctrl+C для остановки.")
        )
        app.run_polling()
