from django.shortcuts import render


def index(request):
    return render(request, "index.html", {})

def maintenance(request):
    return render(request, "maintenance.html", {})
