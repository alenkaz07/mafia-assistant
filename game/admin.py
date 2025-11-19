from django.contrib import admin
from .models import Mode, Role, Session, Phase, Player, Vote, Result, Profile


@admin.register(Mode)
class ModeAdmin(admin.ModelAdmin):
    list_display = ("name", "min_players", "max_players")
    search_fields = ("name",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_unique", "turn_order")
    list_filter = ("is_unique",)
    search_fields = ("name",)


class PlayerInline(admin.TabularInline):
    model = Player
    extra = 0


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("id", "mode", "host", "status", "players_count", "created_at", "finished_at")
    list_filter = ("status", "mode")
    search_fields = ("id", "mode__name", "host__username")
    date_hierarchy = "created_at"
    inlines = [PlayerInline]


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    ordering = ("order",)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "name",
        "role",
        "status",
        "seat_number",
    )
    list_filter = ("session", "status", "role")
    search_fields = ("name", "session__id")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("session", "round_number", "phase", "voter", "target")
    list_filter = ("phase", "round_number", "session")
    search_fields = ("session__id", "voter__name", "target__name")


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("session", "winner_side", "rounds_count", "mafia_count", "town_count")
    list_filter = ("winner_side",)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
