import json
from pathlib import Path
from tempfile import TemporaryDirectory

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

    def make_question(self, skill):
        question = Question.objects.create(skill=skill, prompt=f"{skill.name}?")
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

        self.client.post(
            reverse("grind:submit_answer", args=[first_question.id]),
            {"choice": first_correct_choice.id},
        )
        self.client.post(
            reverse("grind:submit_answer", args=[second_question.id]),
            {"choice": second_incorrect_choice.id},
        )

        competence = UserSkillCompetence.objects.get(user=self.user, skill=self.skill)
        self.assertEqual(competence.competence, 0.5)
        domain_elo = UserDomainElo.objects.get(user=self.user, domain=self.domain)
        self.assertEqual(domain_elo.competence, 0.25)
        self.assertEqual(domain_elo.elo, 400)

    def test_user_elo_combines_skill_competence_on_29_skill_scale(self):
        UserSkillCompetence.objects.create(user=self.user, skill=self.skill, competence=0.5)
        UserSkillCompetence.objects.create(user=self.user, skill=self.other_skill, competence=1.0)

        user_elo = UserElo.recalculate_for(self.user)

        self.assertEqual(user_elo.elo, round((1600 / 29) * 1.5))

    def test_user_domain_elo_averages_skill_competence_in_domain(self):
        UserSkillCompetence.objects.create(user=self.user, skill=self.skill, competence=0.5)
        UserSkillCompetence.objects.create(user=self.user, skill=self.other_skill, competence=1.0)

        domain_elo = UserDomainElo.recalculate_for(self.user, self.domain)

        self.assertEqual(domain_elo.competence, 0.75)
        self.assertEqual(domain_elo.elo, 1200)


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
