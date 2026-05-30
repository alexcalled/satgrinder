# Create your views here.
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def landing(request):
    if request.user.is_authenticated:
        return redirect(home)
    return render(request, "landing.html")


@login_required
def home(request):
    return render(request, "home.html")
