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
    UserElo,
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

        self.assertEqual(response.context["elo"], 200)
        self.assertEqual(response.context["questions_solved"], 2)
        self.assertEqual(response.context["minutes_grinding"], 0)
        self.assertEqual(response.context["current_streak"], 1)
        self.assertEqual(response.context["accuracy_rate"], 50)
        self.assertEqual(response.context["domain_groups"][0]["label"], "Math")
        self.assertEqual(response.context["domain_groups"][0]["domains"][0]["rating"], 100)
        self.assertEqual(
            response.context["domain_groups"][0]["domains"][0]["competence_percent"], 50
        )
        self.assertEqual(response.context["domain_groups"][1]["label"], "R&W")
        self.assertEqual(response.context["domain_groups"][1]["domains"][0]["rating"], 100)
        self.assertContains(response, "200 ELO")
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

    def test_leaderboard_renders_top_8_real_elos(self):
        users = [
            get_user_model().objects.create_user(
                username=f"student{i}",
                password="test-password",
            )
            for i in range(10)
        ]
        for index, user in enumerate(users):
            UserElo.objects.create(user=user, elo=1000 + (index * 10))
        self.client.force_login(users[0])

        response = self.client.get(reverse("leaderboard"))

        leaderboard = response.context["leaderboard"]
        self.assertEqual(len(leaderboard["entries"]), 8)
        self.assertEqual(leaderboard["entries"][0]["username"], "student9")
        self.assertEqual(leaderboard["entries"][0]["elo"], 1090)
        self.assertEqual(leaderboard["entries"][-1]["username"], "student2")
        self.assertContains(response, "Top grinders.")
        self.assertContains(response, "@student9")
        self.assertContains(response, "1090 ELO")
        self.assertContains(response, "Live ELO")
        self.assertNotContains(response, "@student1")
        self.assertNotContains(response, "@student0")
        self.assertNotContains(response, "Weekly Scores")
        self.assertNotContains(response, "Static preview")
