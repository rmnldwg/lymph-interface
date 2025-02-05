"""
URLs related to the `riskpredictor` prediction app.

This app is reachable under the URL ``https://lyprox.org/riskpredictor``. Like the
`dataexplorer`, this includes a dashboard and a help page.
"""

from django.urls import path

from lyprox.riskpredictor import views

app_name = "riskpredictor"
urlpatterns = [
    path("add/", views.AddInferenceResultView.as_view(), name="add"),
    path("list/", views.ChooseInferenceResultView.as_view(), name="list"),
    path("<int:pk>/", views.RiskPredictionView.as_view(), name="dashboard"),
    path("<int:pk>/ajax/", views.riskpredictor_ajax_view, name="ajax"),
    path("help/", views.help_view, name="help"),
    path("test/", views.test_view, name="test"),
]
