from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def spa(request: HttpRequest) -> HttpResponse:
    """Serve the built SPA shell, rendered as a Django template.

    Anonymous access is allowed by default (the SPA handles authentication
    against the API itself); set CRUDKIT_FRONTEND_LOGIN_REQUIRED = True to
    redirect anonymous users to settings.LOGIN_URL instead.
    """
    if getattr(settings, "CRUDKIT_FRONTEND_LOGIN_REQUIRED", False) and not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    return render(request, "crudkit_frontend/index.html")
