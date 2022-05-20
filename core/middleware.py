from django.shortcuts import redirect, reverse

from core import settings


class MaintenanceMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        path = request.META.get('PATH_INFO', "")

        if settings.MAINTENANCE and not path == reverse("maintenance"):
            response = redirect(reverse("maintenance"))
            return response

        response = self.get_response(request)
        return response
