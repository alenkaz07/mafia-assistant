from django import forms
from .models import Session, Player


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['mode', 'players_count', 'status']
        labels = {
            'mode': 'Режим игры',
            'players_count': 'Планируемое число игроков',
            'status': 'Статус',
        }


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
