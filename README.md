# Mafia Assistant

Веб-сервис и Telegram-бот, которые помогают ведущему управлять партией в «Мафию»: вести список игроков, роли, фазы, фиксировать результат и смотреть статистику.

> Проект разработан в рамках преддипломной практики.<br>
> Автор: Казарина Алёна Алексеевна<br>
> Начало разработки: 10.11.2025<br>
> Конец разработки: 07.12.2025<br>

## Основные возможности

- управление игровыми сессиями и режимами (классика / спортивная мафия);
- роли с описаниями и порядком хода;
- кабинет ведущего и кабинет игрока;
- Telegram-бот для управления партией.

## Технологии

- Python 3.13.3;
- Django 6.0;
- SQLite (по умолчанию);
- `python-telegram-bot` *Version: 21.7* для Telegram-бота;
- HTML + CSS.

## Установка и запуск (локально)

```bash
git clone git@github.com:alenkaz07/mafia-assistant.git
cd mafia-assistant

python -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser

python manage.py runserver
```

Приложение будет доступно по адресу http://localhost:8000/
