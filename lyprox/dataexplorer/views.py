"""
The `views` module in the `dataexplorer` app mostly handles the
`DashboardView`, which takes care of initializing the complex
`forms.DashboardForm`, passing the cleaned values to all the filtering
functions in the `query` module to finally pass the queried information to
the context variable that is rendered into the HTML response.
"""

import json
import logging
from typing import Any

import numpy as np
from django.http.response import HttpResponse, JsonResponse
from django.shortcuts import render
from lydata.utils import get_default_modalities

from lyprox.dataexplorer import query
from lyprox.dataexplorer.forms import DashboardForm
from lyprox.settings import LNLS, SUBSITE_DICT

logger = logging.getLogger(__name__)


def help_view(request) -> HttpResponse:
    """Simply display the dashboard help text."""
    template_name = "dataexplorer/help/index.html"
    context = {"modalities": get_default_modalities()}
    return render(request, template_name, context)


def transform_np_to_lists(stats: dict[str, Any]) -> dict[str, Any]:
    """
    If ``stats`` contains any values that are of type ``np.ndarray``, then they are
    converted to normal lists.
    """
    for key, value in stats.items():
        if isinstance(value, np.ndarray):
            stats[key] = value.tolist()

    return stats


def get_initial_stats(form: DashboardForm) -> dict[str, Any]:
    """Return the initial statistics to be displayed on the dashboard."""
    stats = {
        "total": 42,
        "datasets": {},
        "sex": np.zeros(shape=(3,), dtype=int),
        "nicotine_abuse": np.zeros(shape=(3,), dtype=int),
        "hpv_status": np.zeros(shape=(3,), dtype=int),
        "neck_dissection": np.zeros(shape=(3,), dtype=int),
        "n_status": np.zeros(shape=(3,), dtype=int),
        "subsites": np.zeros(shape=len(SUBSITE_DICT), dtype=int),
        "t_stages": np.zeros(shape=(len(form["t_stage"].initial),), dtype=int),
        "central": np.zeros(shape=(3,), dtype=int),
        "extension": np.zeros(shape=(3,), dtype=int),
    }
    for side in ["ipsi", "contra"]:
        for lnl in LNLS:
            stats[f"{side}_{lnl}"] = np.zeros(shape=(3,), dtype=int)

    return stats


def dashboard_view(request):
    """Return the dashboard view when the user first accesses the dashboard."""
    data = request.GET
    form = DashboardForm(data, user=request.user)
    context = {
        "form": form,
        "modalities": get_default_modalities(),
        "stats": get_initial_stats(form=form),
    }

    if form.is_valid():
        logger.info("Form valid, running query.")
        # stats = run_query(form.cleaned_data)
        # context["stats"] = transform_np_to_lists(stats)
        context["show_percent"] = form.cleaned_data["show_percent"]
        ...

    return render(request, "dataexplorer/layout.html", context)


def dashboard_ajax_view(request):
    """
    View that receives JSON data from the AJAX request and cleans it using the
    same method as the class-based ``DashboardView``.
    """
    data = json.loads(request.body.decode("utf-8"))
    form = DashboardForm(data, user=request.user)

    if form.is_valid():
        logger.info("Form from AJAX request is valid, running query.")
        # stats = run_query(form.cleaned_data)
        # return JsonResponse(data=stats)
        ...

    logger.warning("AJAX form invalid.")
    return JsonResponse(data={"error": "Something went wrong."}, status=400)
