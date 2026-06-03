from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

SAT_ELO_MAX = 1600
DOMAIN_ELO_DEFAULT = 100
DOMAIN_ELO_MAX = 200
QUESTION_CORRECT_POINTS = {
    "easy": 5,
    "medium": 10,
    "hard": 15,
}
QUESTION_INCORRECT_POINTS = {
    "easy": -15,
    "medium": -10,
    "hard": -5,
}
QUESTION_DIFFICULTY_POINTS = QUESTION_CORRECT_POINTS
QUESTION_DIFFICULTY_CHOICES = [
    ("easy", "Easy"),
    ("medium", "Medium"),
    ("hard", "Hard"),
]


# SAT category, highest classification tier
class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# SAT domain, second classification tier
class Domain(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="domains")
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.category} —— {self.name}"


# SAT skill, third classification tier
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
    )
    prompt = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    difficulty = models.CharField(choices=QUESTION_DIFFICULTY_CHOICES, default="medium")
    is_active = models.BooleanField(default=True)

    # Logic for elo gained/lost by question
    @property
    def elo_points(self):
        return QUESTION_CORRECT_POINTS.get(self.difficulty, QUESTION_CORRECT_POINTS["medium"])

    def elo_delta_for_result(self, is_correct):
        if is_correct:
            points = QUESTION_CORRECT_POINTS
        else:
            points = QUESTION_INCORRECT_POINTS
        return points.get(self.difficulty, points["medium"])

    def __str__(self):
        return self.prompt[:50]


class UserSkillCompetence(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skill_competences"
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="user_competences")
    competence = models.FloatField(
        default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    updated_at = models.DateTimeField(auto_now=True)

    # Calculates competence as correct rate for its skill, updates
    @classmethod
    def recalculate_for(cls, user, skill):
        attempts = QuestionAttempt.objects.filter(user=user, question__skill=skill)
        attempt_count = attempts.count()
        competence = 0.0

        if attempt_count > 0:
            correct_count = attempts.filter(is_correct=True).count()
            competence = correct_count / attempt_count

        user_skill_competence, _ = cls.objects.update_or_create(
            user=user, skill=skill, defaults={"competence": competence}
        )
        return user_skill_competence

    def __str__(self):
        return f"{self.user} —— {self.skill}: {self.competence:.2f}"


class UserElo(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="elo_stat"
    )
    elo = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(SAT_ELO_MAX)]
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def recalculate_for(cls, user):
        domain_elos = UserDomainElo.recalculate_all_for(user)
        elo = sum(domain_elo.elo for domain_elo in domain_elos)
        elo = max(0, min(SAT_ELO_MAX, elo))

        user_elo, _ = cls.objects.update_or_create(user=user, defaults={"elo": elo})
        return user_elo

    def __str__(self):
        return f"{self.user} —— {self.elo} ELO"


class UserDomainElo(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="domain_elos"
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="user_elos")
    competence = models.FloatField(
        default=0.5, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    elo = models.IntegerField(
        default=DOMAIN_ELO_DEFAULT,
        validators=[MinValueValidator(0), MaxValueValidator(DOMAIN_ELO_MAX)],
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def score_for(cls, user, domain, exclude_attempt_id=None):
        attempts = QuestionAttempt.objects.filter(
            user=user, question__skill__domain=domain
        ).select_related("question")

        if exclude_attempt_id:
            attempts = attempts.exclude(id=exclude_attempt_id)

        elo = DOMAIN_ELO_DEFAULT + sum(
            attempt.question.elo_delta_for_result(attempt.is_correct) for attempt in attempts
        )
        return max(0, min(DOMAIN_ELO_MAX, elo))

    @classmethod
    def recalculate_for(cls, user, domain):
        elo = cls.score_for(user, domain)
        competence = elo / DOMAIN_ELO_MAX
        user_domain_elo, _ = cls.objects.update_or_create(
            user=user, domain=domain, defaults={"competence": competence, "elo": elo}
        )
        return user_domain_elo

    @classmethod
    def recalculate_all_for(cls, user):
        domains = Domain.objects.filter(is_active=True, category__is_active=True)
        return [cls.recalculate_for(user, domain) for domain in domains]

    def __str__(self):
        return f"{self.user} —— {self.domain}: {self.elo} ELO"


class AnswerChoice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.TextField()
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text[:50]


class QuestionAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="question_attempts"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="attempts")
    selected_choice = models.ForeignKey(
        AnswerChoice, on_delete=models.CASCADE, related_name="attempts"
    )
    is_correct = models.BooleanField(default=True)
    time_attempted = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.is_correct = self.selected_choice.is_correct
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} —— {self.question}"
