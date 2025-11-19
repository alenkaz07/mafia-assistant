"""
URL configuration for mafia_assistant project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from game import views as game_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path(
        'login/',
        auth_views.LoginView.as_view(template_name='game/login.html'),
        name='login',
    ),

    # используем свой logout
    path('logout/', game_views.logout_view, name='logout'),

    path('register/', game_views.register, name='register'),
    path('cabinet/', game_views.cabinet, name='cabinet'),

    path('', include('game.urls')),
]

handler404 = 'game.views.custom_404'
