from django.core.management.base import BaseCommand
from django.conf import settings

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)


class Command(BaseCommand):
    help = "Запуск Telegram-бота для мафии"

    async def start_cmd(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Обработчик /start в телеграме."""
        text = (
            "Привет! Я бот-ассистент для игры в мафию.\n\n"
            "Пока я умею немного:\n"
            " /start — приветствие\n"
            " /help — список команд\n\n"
            "/startgame, /addplayer, /next и т.д."
        )
        if update.message:
            await update.message.reply_text(text)

    async def help_cmd(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Обработчик /help."""
        text = (
            "Команды бота:\n"
            " /start — приветствие\n"
            " /help — эта справка\n"
            "\n"
            " /startgame — создать игру\n"
            " /addplayer Имя — добавить игрока\n"
            " /next — перейти к следующей фазе\n"
            "Автор: Казарина Алёна Алексеевна\n"
        )
        if update.message:
            await update.message.reply_text(text)

    def handle(self, *args, **options):
        """Точка входа management-команды."""
        token = getattr(settings, "TG_BOT_TOKEN", None)
        if not token:
            self.stderr.write(
                self.style.ERROR(
                    "В settings.py не найден TG_BOT_TOKEN. "
                )
            )
            return

        app = ApplicationBuilder().token(token).build()

        # Регистрируем обработчики команд
        app.add_handler(CommandHandler("start", self.start_cmd))
        app.add_handler(CommandHandler("help", self.help_cmd))

        self.stdout.write(self.style.SUCCESS("Бот запущен. Нажми Ctrl+C для остановки."))
        # Запуск long-polling
        app.run_polling()
