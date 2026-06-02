from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

SAT_ELO_MAX = 1600
SAT_SKILL_COUNT = 29


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


class UserSkillCompetence(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skill_competences"
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="user_competences")
    competence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "skill"],
                name="unique_competence_per_user_skill",
            )
        ]

    @classmethod
    def recalculate_for(cls, user, skill):
        attempts = QuestionAttempt.objects.filter(user=user, question__skill=skill)
        attempt_count = attempts.count()
        competence = 0.0

        if attempt_count:
            correct_count = attempts.filter(is_correct=True).count()
            competence = correct_count / attempt_count

        user_skill_competence, _ = cls.objects.update_or_create(
            user=user,
            skill=skill,
            defaults={"competence": competence},
        )
        return user_skill_competence

    def __str__(self):
        return f"{self.user} —— {self.skill}: {self.competence:.2f}"


class UserElo(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="elo_stat"
    )
    elo = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(SAT_ELO_MAX)],
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def recalculate_for(cls, user):
        competence_total = sum(
            UserSkillCompetence.objects.filter(user=user).values_list("competence", flat=True)
        )
        elo = round((SAT_ELO_MAX / SAT_SKILL_COUNT) * competence_total)
        elo = max(0, min(SAT_ELO_MAX, elo))

        user_elo, _ = cls.objects.update_or_create(
            user=user,
            defaults={"elo": elo},
        )
        return user_elo

    def __str__(self):
        return f"{self.user} —— {self.elo} ELO"


class UserDomainElo(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="domain_elos"
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="user_elos")
    competence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    elo = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(SAT_ELO_MAX)],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "domain"],
                name="unique_domain_elo_per_user_domain",
            )
        ]

    @classmethod
    def recalculate_for(cls, user, domain):
        skills = domain.skills.filter(is_active=True)
        skill_count = skills.count()
        competence_total = sum(
            UserSkillCompetence.objects.filter(user=user, skill__in=skills).values_list(
                "competence", flat=True
            )
        )
        competence = competence_total / skill_count if skill_count else 0.0
        competence = max(0.0, min(1.0, competence))
        elo = round(SAT_ELO_MAX * competence)

        user_domain_elo, _ = cls.objects.update_or_create(
            user=user,
            domain=domain,
            defaults={
                "competence": competence,
                "elo": elo,
            },
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
    )  # check
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="attempts")
    selected_choice = models.ForeignKey(
        AnswerChoice, on_delete=models.CASCADE, related_name="attempts"
    )
    is_correct = models.BooleanField(default=True)  # change this
    time_attempted = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.is_correct = self.selected_choice.is_correct
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} —— {self.question}"
