import random

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    DOMAIN_ELO_MAX,
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

CATEGORY_LABELS = {
    "reading": "Reading",
    "writing": "Writing",
    "math": "Math",
}

QUESTION_SELECTION_WEIGHT_FLOOR = 0.05
DOMAIN_CATEGORY_ORDER = {"math": 0, "reading": 1, "writing": 2}


def score_delta_label(delta):
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def get_score_domains():
    domains = list(
        Domain.objects.filter(is_active=True, category__is_active=True).select_related("category")
    )
    domains.sort(
        key=lambda domain: (DOMAIN_CATEGORY_ORDER.get(domain.category.slug, 3), domain.name)
    )
    return domains


def build_score_state(user, exclude_attempt_id=None):
    domain_scores = []

    for domain in get_score_domains():
        score = UserDomainElo.score_for(
            user,
            domain,
            exclude_attempt_id=exclude_attempt_id,
        )
        domain_scores.append(
            {
                "id": domain.id,
                "name": domain.name,
                "score": score,
                "percent": round((score / DOMAIN_ELO_MAX) * 100),
            }
        )

    return {
        "overall": sum(domain["score"] for domain in domain_scores),
        "domains": domain_scores,
    }


def build_score_change(user, attempt):
    before = build_score_state(user, exclude_attempt_id=attempt.id)
    after = build_score_state(user)
    before_domains = {domain["id"]: domain for domain in before["domains"]}
    domains = []

    for after_domain in after["domains"]:
        before_domain = before_domains[after_domain["id"]]
        delta = after_domain["score"] - before_domain["score"]
        domains.append(
            {
                "name": after_domain["name"],
                "before": before_domain["score"],
                "after": after_domain["score"],
                "before_percent": before_domain["percent"],
                "after_percent": after_domain["percent"],
                "delta": delta,
                "delta_label": score_delta_label(delta),
            }
        )

    overall_delta = after["overall"] - before["overall"]
    return {
        "overall_before": before["overall"],
        "overall_after": after["overall"],
        "overall_delta": overall_delta,
        "overall_delta_label": score_delta_label(overall_delta),
        "domains": domains,
    }


# Selects question, probability of selection weighted by competence
def select_weighted_question(user, selected_skill_ids):
    attempted_question_ids = QuestionAttempt.objects.filter(
        user=user,
    ).values_list("question_id", flat=True)

    questions = list(
        Question.objects.filter(
            skill_id__in=selected_skill_ids,
            is_active=True,
        )
        .exclude(id__in=attempted_question_ids)
        .select_related("skill", "skill__domain", "skill__domain__category")
        .prefetch_related("choices")
        .order_by("id")
    )

    if not questions:
        return None

    competences = dict(
        UserSkillCompetence.objects.filter(
            user=user,
            skill_id__in=selected_skill_ids,
        ).values_list("skill_id", "competence")
    )
    weights = [
        max(QUESTION_SELECTION_WEIGHT_FLOOR, 1 - competences.get(question.skill_id, 0.0))
        for question in questions
    ]
    return random.choices(questions, weights=weights, k=1)[0]


@login_required
def category_select(request):
    return render(request, "grind.html")


@login_required
def category_modal(request, category_slug):


    return render(
        request,
        "partials/grind_modal.html",
        {
            "category_slug": category_slug,
            "category_name": CATEGORY_LABELS[category_slug],
        },
    )


@login_required
def custom_modal(request):
    return render(request, "partials/custom_wip_modal.html")


@login_required
@require_POST
def start_category(request, category_slug):
    category = get_object_or_404(
        Category,
        slug=category_slug,
        is_active=True,
    )

    selected_skill_ids = list(
        Skill.objects.filter(
            domain__category=category,
            domain__is_active=True,
            is_active=True,
        ).values_list("id", flat=True)
    )

    if not selected_skill_ids:
        return redirect("grind:category_select")

    request.session["selected_skill_ids"] = selected_skill_ids
    request.session["selected_category_slug"] = category.slug

    return redirect("grind:terminal")


@login_required
def terminal(request):
    selected_skill_ids = request.session.get("selected_skill_ids", [])

    if not selected_skill_ids:
        return redirect("grind:category_select")

    question = select_weighted_question(request.user, selected_skill_ids)

    return render(request, "terminal.html", {"question": question})


# Gets question, choice to make QuestionAttempt. Recalculates all user stats.
@login_required
@require_POST
def submit_answer(request, question_id):
    selected_skill_ids = request.session.get("selected_skill_ids", [])

    if not selected_skill_ids:
        return redirect("grind:category_select")

    question = get_object_or_404(
        Question,
        id=question_id,
        skill_id__in=selected_skill_ids,
        is_active=True,
    )

    choice_id = request.POST.get("choice")

    selected_choice = get_object_or_404(
        AnswerChoice,
        id=choice_id,
        question=question,
    )

    attempt, _ = QuestionAttempt.objects.get_or_create(
        user=request.user,
        question=question,
        defaults={
            "selected_choice": selected_choice,
        },
    )
    UserSkillCompetence.recalculate_for(request.user, question.skill)
    UserDomainElo.recalculate_for(request.user, question.skill.domain)
    UserElo.recalculate_for(request.user)
    request.session[f"score_change_{attempt.id}"] = build_score_change(request.user, attempt)

    return redirect("grind:answer_result", attempt_id=attempt.id)


# Creates answer review page after submission.
@login_required
def answer_result(request, attempt_id):
    attempt = get_object_or_404(
        QuestionAttempt.objects.select_related(
            "question",
            "question__skill",
            "question__skill__domain",
            "question__skill__domain__category",
            "selected_choice",
        ).prefetch_related("question__choices"),
        id=attempt_id,
        user=request.user,
    )
    selected_skill_ids = request.session.get("selected_skill_ids", [])

    #prevents accessing attempt from other user
    if selected_skill_ids and attempt.question.skill_id not in selected_skill_ids:
        raise Http404("Attempt does not belong to this grind session.")

    correct_choice = attempt.question.choices.filter(is_correct=True).first()

    return render(
        request,
        "terminal.html",
        {
            "answer_attempt": attempt,
            "question": attempt.question,
            "correct_choice": correct_choice,
        },
    )


# Finds change in score for elo change screen after question review
@login_required
def score_summary(request, attempt_id):
    attempt = get_object_or_404(
        QuestionAttempt.objects.select_related("question", "question__skill"),
        id=attempt_id,
        user=request.user,
    )
    selected_skill_ids = request.session.get("selected_skill_ids", [])

    if selected_skill_ids and attempt.question.skill_id not in selected_skill_ids:
        raise Http404("Attempt does not belong to this grind session.")

    score_change = request.session.get(f"score_change_{attempt.id}") or build_score_change(
        request.user,
        attempt,
    )

    return render(request, "terminal.html", {"score_change": score_change})


@login_required
def close_modal(request):
    return HttpResponse("")
