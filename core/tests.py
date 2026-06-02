from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from grinder.models import (
    AnswerChoice,
    Category,
    Domain,
    Question,
    QuestionAttempt,
    Skill,
    UserSkillCompetence,
)


class HomeDashboardTests(TestCase):
    def test_home_displays_collected_user_stats(self):
        user = get_user_model().objects.create_user(username="student", password="test-password")
        category = Category.objects.create(name="Math", slug="math")
        reading_category = Category.objects.create(name="Reading", slug="reading")
        domain = Domain.objects.create(category=category, name="Algebra", slug="algebra")
        Domain.objects.create(
            category=reading_category,
            name="Information and Ideas",
            slug="information-and-ideas",
        )
        skill = Skill.objects.create(
            domain=domain, name="Linear equations", slug="linear-equations"
        )
        first_question = Question.objects.create(skill=skill, prompt="First?")
        second_question = Question.objects.create(skill=skill, prompt="Second?")
        first_correct_choice = AnswerChoice.objects.create(
            question=first_question, text="Correct", is_correct=True
        )
        second_incorrect_choice = AnswerChoice.objects.create(
            question=second_question, text="Incorrect", is_correct=False
        )
        QuestionAttempt.objects.create(
            user=user, question=first_question, selected_choice=first_correct_choice
        )
        QuestionAttempt.objects.create(
            user=user, question=second_question, selected_choice=second_incorrect_choice
        )
        UserSkillCompetence.recalculate_for(user, skill)
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.context["elo"], round((1600 / 29) * 0.5))
        self.assertEqual(response.context["questions_solved"], 2)
        self.assertEqual(response.context["minutes_grinding"], 0)
        self.assertEqual(response.context["current_streak"], 1)
        self.assertEqual(response.context["accuracy_rate"], 50)
        self.assertEqual(response.context["domain_groups"][0]["label"], "Math")
        self.assertEqual(response.context["domain_groups"][0]["domains"][0]["rating"], 800)
        self.assertEqual(
            response.context["domain_groups"][0]["domains"][0]["competence_percent"], 50
        )
        self.assertEqual(response.context["domain_groups"][1]["label"], "R&W")
        self.assertEqual(response.context["domain_groups"][1]["domains"][0]["rating"], 0)
        self.assertContains(response, f"{round((1600 / 29) * 0.5)} ELO")
        self.assertContains(response, "Algebra")
        self.assertContains(response, "Information and Ideas")
        self.assertContains(response, "2")
        self.assertContains(response, "50%")

    def test_home_shows_admin_badge_for_staff_user(self):
        user = get_user_model().objects.create_user(
            username="admin-student",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, '<span class="admin-badge">Admin</span>')

    def test_leaderboard_renders_static_preview(self):
        user = get_user_model().objects.create_user(username="student", password="test-password")
        self.client.force_login(user)

        response = self.client.get(reverse("leaderboard"))

        self.assertContains(response, "Top grinders.")
        self.assertContains(response, "1600 ELO")
        self.assertContains(response, "Static preview")
