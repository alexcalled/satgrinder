import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from grinder.models import QUESTION_DIFFICULTY_POINTS, AnswerChoice, Question, Skill

# Example import format:

# {
#   "questions": [
#     {
#       "skill": "linear-equations",
#       "prompt": "Solve 2x + 4 = 10.",
#       "explanation": "Subtract 4 from both sides, then divide by 2.",
#       "difficulty": "easy"
#       "choices": [
#         { "text": "2", "is_correct": false },
#         { "text": "3", "is_correct": true },
#         { "text": "4", "is_correct": false },
#         { "text": "5", "is_correct": false }
#       ]
#     }
#   ]
# }

# skills:
# equivalent-expressions
# nonlinear-equations-in-one-variable-and-systems-of
# nonlinear-functions
# linear-equations-in-one-variable
# linear-equations-in-two-variables
# linear-functions
# linear-inequalities-in-one-or-two-variables
# systems-of-two-linear-equations-in-two-variables
# area-and-volume
# circles
# lines-angles-and-triangles
# right-triangles-and-trigonometry
# evaluating-statistical-claims-observational-studie
# inference-from-sample-statistics-and-margin-of-err
# one-variable-data-distributions-and-measures-of-ce
# percentages
# probability-and-conditional-probability
# ratios-rates-proportional-relationships-and-units
# two-variable-data-models-and-scatterplots
# cross-text-connections
# text-structure-and-purpose
# words-in-context
# central-ideas-and-details
# command-of-evidence
# inferences
# rhetorical-synthesis
# transitions
# boundaries
# form-structure-and-sense


class Command(BaseCommand):
    help = "Import questions and answer choices from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to a JSON question import file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the file without creating or updating questions.",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help=(
                "Update the first question with the same skill and prompt instead of creating one."
            ),
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        questions = self.load_questions(path)
        parsed_questions = [
            self.parse_question(index, item) for index, item in enumerate(questions, 1)
        ]

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Validated {len(parsed_questions)} question(s)."))
            return

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for question_data in parsed_questions:
                question, created = self.save_question(
                    question_data,
                    update_existing=options["update_existing"],
                )
                created_count += int(created)
                updated_count += int(not created)
                self.save_choices(question, question_data["choices"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {created_count} question(s), updated {updated_count} question(s)."
            )
        )

    def load_questions(self, path):
        if not path.exists():
            raise CommandError(f"Import file does not exist: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise CommandError(f"Invalid JSON: {error}") from error

        questions = data.get("questions") if isinstance(data, dict) else data

        if not isinstance(questions, list):
            raise CommandError('Import file must be a list or an object with a "questions" list.')

        return questions

    def parse_question(self, index, item):
        if not isinstance(item, dict):
            raise CommandError(f"Question #{index} must be an object.")

        skill_slug = item.get("skill")
        prompt = item.get("prompt")
        difficulty = item.get("difficulty", "medium")
        choices = item.get("choices")

        if not skill_slug:
            raise CommandError(f'Question #{index} is missing "skill".')

        if not prompt:
            raise CommandError(f'Question #{index} is missing "prompt".')

        if not isinstance(choices, list) or len(choices) < 2:
            raise CommandError(f'Question #{index} must include at least two "choices".')

        if difficulty not in QUESTION_DIFFICULTY_POINTS:
            valid_difficulties = ", ".join(QUESTION_DIFFICULTY_POINTS)
            raise CommandError(
                f'Question #{index} uses invalid difficulty "{difficulty}". '
                f"Use one of: {valid_difficulties}."
            )

        try:
            skill = Skill.objects.get(slug=skill_slug)
        except Skill.DoesNotExist as error:
            raise CommandError(f'Question #{index} uses unknown skill "{skill_slug}".') from error

        parsed_choices = [
            self.parse_choice(index, choice_index, choice)
            for choice_index, choice in enumerate(choices, 1)
        ]
        correct_count = sum(choice["is_correct"] for choice in parsed_choices)

        if correct_count != 1:
            raise CommandError(f"Question #{index} must have exactly one correct choice.")

        return {
            "skill": skill,
            "prompt": prompt,
            "explanation": item.get("explanation", ""),
            "difficulty": difficulty,
            "is_active": item.get("is_active", True),
            "choices": parsed_choices,
        }

    def parse_choice(self, question_index, choice_index, item):
        if not isinstance(item, dict):
            raise CommandError(
                f"Question #{question_index}, choice #{choice_index} must be an object."
            )

        text = item.get("text")

        if not text:
            raise CommandError(
                f'Question #{question_index}, choice #{choice_index} is missing "text".'
            )

        return {
            "text": text,
            "is_correct": bool(item.get("is_correct", False)),
        }

    def save_question(self, question_data, update_existing):
        if update_existing:
            question = Question.objects.filter(
                skill=question_data["skill"],
                prompt=question_data["prompt"],
            ).first()

            if question:
                question.explanation = question_data["explanation"]
                question.difficulty = question_data["difficulty"]
                question.is_active = question_data["is_active"]
                question.save(update_fields=["explanation", "difficulty", "is_active"])
                return question, False

        question = Question.objects.create(
            skill=question_data["skill"],
            prompt=question_data["prompt"],
            explanation=question_data["explanation"],
            difficulty=question_data["difficulty"],
            is_active=question_data["is_active"],
        )
        return question, True

    def save_choices(self, question, choices):
        question.choices.all().delete()
        AnswerChoice.objects.bulk_create(
            [
                AnswerChoice(
                    question=question,
                    text=choice["text"],
                    is_correct=choice["is_correct"],
                )
                for choice in choices
            ]
        )
