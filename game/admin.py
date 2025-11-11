from django.contrib import admin
from .models import Mode, Role, Session, Phase, Player, Vote, Result

# Register your models here.

@admin.register(Mode)
class ModeAdmin(admin.ModelAdmin):
    list_display = ("name", "min_players", "max_players")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_unique", "turn_order")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("id", "mode", "host", "status", "players_count", "created_at", "finished_at")
    list_filter = ("status", "mode")


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("name", "order")


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "session", "role", "status", "seat_number")
    list_filter = ("status", "role")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("session", "round_number", "phase", "voter", "target")


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("session", "winner_side", "rounds_count", "mafia_count", "town_count")
