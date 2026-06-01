from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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


class UserSkillCompetenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student", password="test-password"
        )
        self.category = Category.objects.create(name="Math", slug="math")
        self.domain = Domain.objects.create(
            category=self.category, name="Algebra", slug="algebra"
        )
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

    def test_user_elo_combines_skill_competence_on_29_skill_scale(self):
        UserSkillCompetence.objects.create(
            user=self.user, skill=self.skill, competence=0.5
        )
        UserSkillCompetence.objects.create(
            user=self.user, skill=self.other_skill, competence=1.0
        )

        user_elo = UserElo.recalculate_for(self.user)

        self.assertEqual(user_elo.elo, round((1600 / 29) * 1.5))
