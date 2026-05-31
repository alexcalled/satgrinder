from django.urls import path, re_path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("home/", views.home, name="home"),
    path("signup", views.signup, name="signup"),
    path("grind", views.grind, name="grind"),
    path("leaderboard", views.leaderboard, name="leaderboard"),
    path("grind/modal/close/", views.grind_modal_close, name="grind_modal_close"),
    path("grind/modal/<str:mode>/", views.grind_modal, name="grind_modal"),
    re_path(r"^(?P<path>.*)$", views.catchall_view, name="catchall"),
]
