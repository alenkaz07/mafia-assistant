from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms
from .models import Session, Player


class SessionForm(forms.ModelForm):
    players_count = forms.IntegerField(
        min_value=6,
        label='Планируемое число игроков',
        # error_messages={
        #     'min_value': 'Минимальное количество игроков — 6.',
        # },
    )
    class Meta:
        model = Session
        fields = ['mode', 'players_count', 'status']
        labels = {
            'mode': 'Режим игры',
            'players_count': 'Планируемое число игроков',
            'status': 'Статус',
        }

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get('mode')
        players_count = cleaned_data.get('players_count')

        # если одно из полей не выбрано — дальше не проверяем
        if not mode or players_count is None:
            return cleaned_data

        min_p = mode.min_players
        max_p = mode.max_players

        # 1) если min == max - строгое число игроков (спортивная: 10)
        if min_p == max_p and players_count != min_p:
            self.add_error(
                'players_count',
                f'Для режима «{mode.name}» требуется ровно {min_p} игроков.'
            )
        # 2) обычный диапазон: [min_p, max_p]
        elif not (min_p <= players_count <= max_p):
            self.add_error(
                'players_count',
                f'Для режима «{mode.name}» нужно от {min_p} до {max_p} игроков.'
            )

        return cleaned_data


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'role', 'seat_number', 'status', 'notes']
        labels = {
            'name': 'Имя игрока',
            'role': 'Роль',
            'seat_number': 'Номер места',
            'status': 'Статус',
            'notes': 'Примечание',
        }


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")
        labels = {
            "username": "Логин",
            "first_name": "Имя",
            "last_name": "Фамилия",
            "email": "Email",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Короткие русские подсказки
        self.fields["username"].help_text = (
            "Можно использовать латинские буквы, цифры и символы @/./+/-/_"
        )

        self.fields["password1"].label = "Пароль"
        self.fields["password1"].help_text = (
            "Минимум 8 символов, не слишком простой и не только из цифр."
        )

        self.fields["password2"].label = "Подтверждение пароля"
        self.fields["password2"].help_text = "Введите тот же пароль ещё раз."
