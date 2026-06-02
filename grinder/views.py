from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    AnswerChoice,
    Category,
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


@login_required
def category_select(request):
    return render(request, "grind.html")


@login_required
def category_modal(request, category_slug):
    if category_slug not in CATEGORY_LABELS:
        raise Http404("Invalid grind category.")

    return render(
        request,
        "partials/grind_modal.html",
        {
            "category_slug": category_slug,
            "category_name": CATEGORY_LABELS[category_slug],
        },
    )


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

    attempted_question_ids = QuestionAttempt.objects.filter(
        user=request.user,
    ).values_list("question_id", flat=True)

    question = (
        Question.objects.filter(
            skill_id__in=selected_skill_ids,
            is_active=True,
        )
        .exclude(id__in=attempted_question_ids)
        .select_related("skill", "skill__domain", "skill__domain__category")
        .prefetch_related("choices")
        .order_by("id")
        .first()
    )

    return render(
        request,
        "terminal.html",
        {
            "question": question,
        },
    )


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

    QuestionAttempt.objects.get_or_create(
        user=request.user,
        question=question,
        defaults={
            "selected_choice": selected_choice,
        },
    )
    UserSkillCompetence.recalculate_for(request.user, question.skill)
    UserDomainElo.recalculate_for(request.user, question.skill.domain)
    UserElo.recalculate_for(request.user)

    return redirect("grind:terminal")


@login_required
def close_modal(request):
    return HttpResponse("")
