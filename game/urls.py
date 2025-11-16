from django.urls import path
from . import views

app_name = 'game'

urlpatterns = [
    path('', views.index, name='index'),
    path('rules/', views.rules, name='rules'),
    path('roles/', views.roles, name='roles'),
    path('modes/', views.modes, name='modes'),
    path('sessions/', views.sessions_list, name='sessions_list'),
    path('sitemap/', views.sitemap, name='sitemap'),

    # кабинет ведущего
    path('host/sessions/', views.host_sessions, name='host_sessions'),
    path('host/sessions/create/', views.session_create, name='session_create'),
    path('host/sessions/<int:session_id>/', views.session_manage, name='session_manage'),
    path('host/sessions/<int:session_id>/players/add/', views.player_add, name='player_add'),
    path('host/sessions/<int:session_id>/players/<int:player_id>/toggle/', views.player_toggle_status, name='player_toggle_status'),
    path(
        'host/sessions/<int:session_id>/players/<int:player_id>/toggle/',
        views.player_toggle_status,
        name='player_toggle_status',
    ),
    path(
        'host/sessions/<int:session_id>/start/',
        views.session_start,
        name='session_start',
    ),
    path(
        'host/sessions/<int:session_id>/delete/',
        views.session_delete,
        name='session_delete',
    ),
]
