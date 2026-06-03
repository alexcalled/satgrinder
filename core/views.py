from datetime import timedelta

from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from grinder.models import Domain, QuestionAttempt, UserDomainElo, UserElo


# Gets initials of user for pfp treating - or _ as space
def user_initials(user):
    name = user.get_full_name().strip() or user.username
    parts = [part for part in name.replace("-", " ").replace("_", " ").split() if part]

    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()

    return name[:2].upper()


# Builds domain groups for the info panel on home page
# Simplify logic
def build_domain_groups(user):
    domain_elos = {
        domain_elo.domain_id: domain_elo for domain_elo in UserDomainElo.recalculate_all_for(user)
    }
    domains = list(
        Domain.objects.filter(is_active=True, category__is_active=True).select_related("category")
    )
    category_order = {"reading": 0, "writing": 1, "math": 2}
    domains.sort(key=lambda domain: (category_order.get(domain.category.slug, 3), domain.name))
    groups = {
        "math": {"label": "Math", "slug": "math", "domains": []},
        "rw": {"label": "R&W", "slug": "rw", "domains": []},
    }

    for domain in domains:
        domain_elo = domain_elos.get(domain.id)
        competence = domain_elo.competence if domain_elo else 0.0
        domain_data = {
            "name": domain.name,
            "rating": domain_elo.elo if domain_elo else 0,
            "competence_percent": round(competence * 100),
        }
        group_key = "math" if domain.category.slug == "math" else "rw"
        groups[group_key]["domains"].append(domain_data)

    return [groups["math"], groups["rw"]]


def landing(request):
    if request.user.is_authenticated:
        return redirect(home)
    return render(request, "landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

    # If its a GET request, creates empty creation form.
    # Otherwise creates and saves user into database, logs in
    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()

    return render(request, "registration/signup.html", {"form": form})


@login_required
def home(request):
    attempts = QuestionAttempt.objects.filter(user=request.user)
    questions_solved = attempts.count()
    correct_answers = attempts.filter(is_correct=True).count()
    # Accuracy rate logic
    if questions_solved:
        accuracy_rate = round((correct_answers / questions_solved) * 100)
    else:
        accuracy_rate = 0

    # Streak logic. Starts at today, and counts backwards to see your streak length.
    attempt_dates = {
        timezone.localtime(attempted_at).date()
        for attempted_at in attempts.values_list("time_attempted", flat=True)
    }
    streak_date = timezone.localdate()
    current_streak = 0
    while streak_date in attempt_dates:
        current_streak += 1
        streak_date -= timedelta(days=1)

    user_elo = UserElo.recalculate_for(request.user)
    domain_groups = build_domain_groups(request.user)

    return render(
        request,
        "home.html",
        {
            "elo": user_elo.elo,
            "domain_groups": domain_groups,
            "questions_solved": questions_solved,
            "minutes_grinding": 0,
            "current_streak": current_streak,
            "accuracy_rate": accuracy_rate,
        },
    )


@login_required
def leaderboard(request):
    # orders user elos, keeping top 8
    users = (
        get_user_model()
        .objects.filter(is_active=True, elo_stat__isnull=False)
        .select_related("elo_stat")
        .order_by("-elo_stat__elo", "username")[:8]
    )

    entries = []
    for rank, user in enumerate(users, start=1):
        podium_class = {1: "podium-first", 2: "podium-second", 3: "podium-third"}.get(rank, "")
        entries.append(
            {
                "rank": rank,
                "username": user.username,
                "initials": user_initials(user),
                "elo": user.elo_stat.elo,
                "podium_class": podium_class,
                "is_current_user": user.id == request.user.id,
                "is_admin": user.is_staff or user.is_superuser,
            }
        )

    leaderboard_data = {
        "entries": entries,
        "podium": entries[:3],
        "rows": entries[3:],
    }

    return render(request, "leaderboard.html", {"leaderboard": leaderboard_data})


def catchall_view(request, path):
    return HttpResponse("<h1>404</h1>")
