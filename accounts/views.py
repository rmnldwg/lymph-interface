from django.shortcuts import render

from .forms import SignupRequestForm


def signup_request_view(request):
    """Render form for requesting to be signed up as a user."""
    if request.method == "POST":
        form = SignupRequestForm(request.POST)

        if form.is_valid():
            # TODO: Implement some sort of notification to notify the admin(s)
            #   that a new request has been made and store the request data.
            pass

    else:
        form = SignupRequestForm()

    context = {"form": form}
    return render(request, "accounts/signup_request.html", context)
