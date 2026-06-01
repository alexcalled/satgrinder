from django.contrib import admin

from .models import (
    AnswerChoice,
    Category,
    Domain,
    Question,
    QuestionAttempt,
    Skill,
    UserElo,
    UserSkillCompetence,
)

admin.site.register(Category)
admin.site.register(Question)
admin.site.register(AnswerChoice)
admin.site.register(QuestionAttempt)
admin.site.register(Domain)
admin.site.register(Skill)
admin.site.register(UserSkillCompetence)
admin.site.register(UserElo)
