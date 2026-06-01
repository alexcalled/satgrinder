from django.urls import path, re_path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("home/", views.home, name="home"),
    path("signup", views.signup, name="signup"),
    path("leaderboard", views.leaderboard, name="leaderboard"),
    re_path(r"^(?P<path>.*)$", views.catchall_view, name="catchall"),
]
