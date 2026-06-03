from django.urls import path

from . import views

app_name = "grind"

urlpatterns = [
    path("", views.category_select, name="category_select"),
    path("modal/close/", views.close_modal, name="close_modal"),
    path("modal/custom/", views.custom_modal, name="custom_modal"),
    path("modal/<slug:category_slug>/", views.category_modal, name="category_modal"),
    path("start/<slug:category_slug>/", views.start_category, name="start_category"),
    path("terminal/", views.terminal, name="terminal"),
    path("answer/<int:question_id>/", views.submit_answer, name="submit_answer"),
    path("result/<int:attempt_id>/", views.answer_result, name="answer_result"),
    path("score/<int:attempt_id>/", views.score_summary, name="score_summary"),
]
