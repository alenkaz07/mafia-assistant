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
]
