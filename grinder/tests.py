import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from .models import (
    AnswerChoice,
    Category,
    Domain,
    Question,
    QuestionAttempt,
    Skill,
    UserDomainElo,
    UserElo,
    UserSkillCompetence,
)
from .views import select_weighted_question


class UserSkillCompetenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student", password="test-password"
        )
        self.category = Category.objects.create(name="Math", slug="math")
        self.domain = Domain.objects.create(category=self.category, name="Algebra", slug="algebra")
        self.skill = Skill.objects.create(
            domain=self.domain, name="Linear equations", slug="linear-equations"
        )
        self.other_skill = Skill.objects.create(
            domain=self.domain, name="Quadratics", slug="quadratics"
        )

    def make_question(self, skill, difficulty="medium"):
        question = Question.objects.create(
            skill=skill,
            prompt=f"{skill.name}?",
            difficulty=difficulty,
        )
        correct_choice = AnswerChoice.objects.create(
            question=question, text="Correct", is_correct=True
        )
        incorrect_choice = AnswerChoice.objects.create(
            question=question, text="Incorrect", is_correct=False
        )
        return question, correct_choice, incorrect_choice

    def test_recalculate_for_sets_competence_from_attempt_accuracy(self):
        first_question, first_correct_choice, _ = self.make_question(self.skill)
        second_question, _, second_incorrect_choice = self.make_question(self.skill)
        other_question, other_correct_choice, _ = self.make_question(self.other_skill)

        QuestionAttempt.objects.create(
            user=self.user, question=first_question, selected_choice=first_correct_choice
        )
        QuestionAttempt.objects.create(
            user=self.user, question=second_question, selected_choice=second_incorrect_choice
        )
        QuestionAttempt.objects.create(
            user=self.user, question=other_question, selected_choice=other_correct_choice
        )

        competence = UserSkillCompetence.recalculate_for(self.user, self.skill)

        self.assertEqual(competence.skill, self.skill)
        self.assertEqual(competence.user, self.user)
        self.assertEqual(competence.competence, 0.5)

    def test_submit_answer_updates_skill_competence(self):
        self.client.force_login(self.user)
        first_question, first_correct_choice, _ = self.make_question(self.skill)
        second_question, _, second_incorrect_choice = self.make_question(self.skill)
        session = self.client.session
        session["selected_skill_ids"] = [self.skill.id]
        session.save()

        response = self.client.post(
            reverse("grind:submit_answer", args=[first_question.id]),
            {"choice": first_correct_choice.id},
        )
        first_attempt = QuestionAttempt.objects.get(question=first_question)
        self.assertRedirects(
            response,
            reverse("grind:answer_result", args=[first_attempt.id]),
            fetch_redirect_response=False,
        )
        self.client.post(
            reverse("grind:submit_answer", args=[second_question.id]),
            {"choice": second_incorrect_choice.id},
        )

        competence = UserSkillCompetence.objects.get(user=self.user, skill=self.skill)
        self.assertEqual(competence.competence, 0.5)
        domain_elo = UserDomainElo.objects.get(user=self.user, domain=self.domain)
        self.assertEqual(domain_elo.competence, 0.5)
        self.assertEqual(domain_elo.elo, 100)
        user_elo = UserElo.objects.get(user=self.user)
        self.assertEqual(user_elo.elo, 100)

    def test_user_elo_sums_domain_elos(self):
        first_question, first_correct_choice, _ = self.make_question(self.skill, difficulty="hard")
        second_question, second_correct_choice, _ = self.make_question(
            self.other_skill, difficulty="easy"
        )
        QuestionAttempt.objects.create(
            user=self.user, question=first_question, selected_choice=first_correct_choice
        )
        QuestionAttempt.objects.create(
            user=self.user, question=second_question, selected_choice=second_correct_choice
        )

        user_elo = UserElo.recalculate_for(self.user)

        self.assertEqual(user_elo.elo, 120)

    def test_user_domain_elo_adds_difficulty_points_for_correct_answers(self):
        first_question, first_correct_choice, _ = self.make_question(self.skill, difficulty="easy")
        second_question, second_correct_choice, _ = self.make_question(
            self.other_skill, difficulty="hard"
        )
        third_question, _, third_incorrect_choice = self.make_question(
            self.other_skill, difficulty="medium"
        )
        QuestionAttempt.objects.create(
            user=self.user, question=first_question, selected_choice=first_correct_choice
        )
        QuestionAttempt.objects.create(
            user=self.user, question=second_question, selected_choice=second_correct_choice
        )
        QuestionAttempt.objects.create(
            user=self.user, question=third_question, selected_choice=third_incorrect_choice
        )

        domain_elo = UserDomainElo.recalculate_for(self.user, self.domain)

        self.assertEqual(domain_elo.competence, 0.55)
        self.assertEqual(domain_elo.elo, 110)

    def test_user_domain_elo_defaults_to_100_without_attempts(self):
        domain_elo = UserDomainElo.recalculate_for(self.user, self.domain)

        self.assertEqual(domain_elo.competence, 0.5)
        self.assertEqual(domain_elo.elo, 100)

    def test_question_selection_weights_lower_competence_skills_more_heavily(self):
        strong_question, _, _ = self.make_question(self.skill)
        weak_question, _, _ = self.make_question(self.other_skill)
        UserSkillCompetence.objects.create(
            user=self.user,
            skill=self.skill,
            competence=1.0,
        )
        UserSkillCompetence.objects.create(
            user=self.user,
            skill=self.other_skill,
            competence=0.0,
        )

        with patch("grinder.views.random.choices", return_value=[weak_question]) as choices:
            question = select_weighted_question(
                self.user,
                [self.skill.id, self.other_skill.id],
            )

        self.assertEqual(question, weak_question)
        self.assertEqual(choices.call_args.kwargs["weights"], [0.05, 1.0])
        self.assertEqual(choices.call_args.args[0], [strong_question, weak_question])

    def test_answer_result_shows_feedback_and_explanation(self):
        self.client.force_login(self.user)
        question = Question.objects.create(
            skill=self.skill,
            prompt="What is x?",
            explanation="x is 3 because the equation balances there.",
            difficulty="medium",
        )
        correct_choice = AnswerChoice.objects.create(
            question=question,
            text="3",
            is_correct=True,
        )
        selected_choice = AnswerChoice.objects.create(
            question=question,
            text="4",
            is_correct=False,
        )
        attempt = QuestionAttempt.objects.create(
            user=self.user,
            question=question,
            selected_choice=selected_choice,
        )
        session = self.client.session
        session["selected_skill_ids"] = [self.skill.id]
        session.save()

        response = self.client.get(reverse("grind:answer_result", args=[attempt.id]))

        self.assertContains(response, "Almost.")
        self.assertContains(response, "answer-review-row-wrong")
        self.assertContains(response, "answer-review-row-correct")
        self.assertContains(response, selected_choice.text)
        self.assertContains(response, correct_choice.text)
        self.assertContains(response, "x is 3 because the equation balances there.")

    def test_score_summary_shows_before_after_and_domain_deltas(self):
        self.client.force_login(self.user)
        question, correct_choice, _ = self.make_question(self.skill, difficulty="hard")
        attempt = QuestionAttempt.objects.create(
            user=self.user,
            question=question,
            selected_choice=correct_choice,
        )
        session = self.client.session
        session["selected_skill_ids"] = [self.skill.id]
        session.save()

        response = self.client.get(reverse("grind:score_summary", args=[attempt.id]))

        self.assertContains(response, 'data-start="100"')
        self.assertContains(response, 'data-end="115"')
        self.assertContains(response, "+15")
        self.assertContains(response, self.domain.name)


class ImportQuestionsCommandTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Math", slug="math")
        domain = Domain.objects.create(category=category, name="Algebra", slug="algebra")
        self.skill = Skill.objects.create(
            domain=domain,
            name="Linear equations",
            slug="linear-equations",
        )

    def write_import_file(self, data):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "questions.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_import_questions_creates_question_and_choices(self):
        path = self.write_import_file(
            {
                "questions": [
                    {
                        "skill": self.skill.slug,
                        "prompt": "Solve 2x + 4 = 10.",
                        "explanation": "Subtract 4, then divide by 2.",
                        "difficulty": "hard",
                        "choices": [
                            {"text": "2", "is_correct": False},
                            {"text": "3", "is_correct": True},
                            {"text": "4", "is_correct": False},
                            {"text": "5", "is_correct": False},
                        ],
                    }
                ]
            }
        )

        call_command("import_questions", path)

        question = Question.objects.get(prompt="Solve 2x + 4 = 10.")
        self.assertEqual(question.skill, self.skill)
        self.assertEqual(question.explanation, "Subtract 4, then divide by 2.")
        self.assertEqual(question.difficulty, "hard")
        self.assertEqual(question.choices.count(), 4)
        self.assertEqual(question.choices.get(is_correct=True).text, "3")

    def test_import_questions_rejects_questions_without_one_correct_choice(self):
        path = self.write_import_file(
            [
                {
                    "skill": self.skill.slug,
                    "prompt": "Pick the correct answer.",
                    "choices": [
                        {"text": "A", "is_correct": False},
                        {"text": "B", "is_correct": False},
                    ],
                }
            ]
        )

        with self.assertRaises(CommandError):
            call_command("import_questions", path)
