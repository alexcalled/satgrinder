from django.conf import settings
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Domain(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="domains")
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.category} —— {self.name}"


class Skill(models.Model):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.domain} —— {self.name}"


class Question(models.Model):
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="questions", null=True, blank=True
    )  # change
    prompt = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.prompt[:50]


class AnswerChoice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.TextField()
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text[:50]


class QuestionAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="question_attempts"
    )  # check
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="attempts")
    selected_choice = models.ForeignKey(
        AnswerChoice, on_delete=models.CASCADE, related_name="attempts"
    )
    is_correct = models.BooleanField(default=True)  # change this
    time_attempted = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.is_correct = self.selected_choice.is_correct
        super.save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} —— {self.question}"
