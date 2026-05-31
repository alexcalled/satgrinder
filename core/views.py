from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render


def landing(request):
    if request.user.is_authenticated:
        return redirect(home)
    return render(request, "landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

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
    return render(request, "home.html")


@login_required
def leaderboard(request):
    return render(request, "leaderboard.html")


@login_required
def grind(request):
    return render(request, "grind.html")


def grind_modal(request, mode):
    mode_labels = {
        "reading": "Reading",
        "writing": "Writing",
        "math": "Math",
    }

    if mode not in mode_labels:
        raise Http404("Invalid grind mode.")

    return render(
        request,
        "partials/grind_modal.html",
        {
            "mode": mode,
            "mode_label": mode_labels[mode],
        },
    )


def grind_modal_close(request):
    return HttpResponse("")


def catchall_view(request, path):
    return HttpResponse("<h1>404</h1>")
