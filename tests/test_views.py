from typing import List

import pytest
from django import urls

from patients.models import Diagnose, Tumor


@pytest.mark.django_db
def _assemble_kwargs(patient_factory, tumor_factory, diagnose_factory,
                     required_kwargs: List[str]):
    """Create Patient, Tumor and Diagnoses for testing the views.
    """
    patient = patient_factory.create()
    tumor = tumor_factory.create(patient=patient)
    diagnose = diagnose_factory.create(patient=patient)

    kwargs = {}
    if required_kwargs is None:
        return kwargs

    if "pk" in required_kwargs:
        kwargs["pk"] = patient.pk
    if "tumor_pk" in required_kwargs:
        kwargs["tumor_pk"] = Tumor.objects.filter(patient=patient).first().pk
    if "diagnose_pk" in required_kwargs:
        kwargs["diagnose_pk"] = Diagnose.objects.filter(patient=patient).first().pk

    return kwargs


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name, required_kwargs",
    [("patients:upload", None),
     ("patients:download", None),
     ("patients:create", None),
     ("patients:update", ["pk"]),
     ("patients:delete", ["pk"]),
     ("patients:tumor_create", ["pk"]),
     ("patients:tumor_update", ["pk", "tumor_pk"]),
     ("patients:tumor_delete", ["pk", "tumor_pk"]),
     ("patients:diagnose_create", ["pk"]),
     ("patients:diagnose_update", ["pk", "diagnose_pk"]),
     ("patients:diagnose_delete", ["pk", "diagnose_pk"])]
)
def test_restricted_views(
    client, url_name,
    patient_factory, tumor_factory, diagnose_factory,
    required_kwargs
):
    """Make sure that websites that shoud only be accessible to logged-in users
    redirect to the login page.
    """
    kwargs = _assemble_kwargs(
        patient_factory, tumor_factory, diagnose_factory,
        required_kwargs=required_kwargs
    )
    reversed_url = urls.reverse(url_name, kwargs=kwargs)
    response = client.get(reversed_url)
    assert response.status_code == 302
    assert urls.reverse("accounts:login") in response.url


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name, required_kwargs",
    [("index", None),
     ("patients:list", None),
     ("dashboard:dashboard", None),
     ("accounts:login", None),
     ("accounts:signup_request", None),
     ("patients:detail", ["pk"])]
)
def test_unrestricted_views(
    client, url_name,
    patient_factory, tumor_factory, diagnose_factory,
    required_kwargs
):
    """Assert that these sites can be viewed by anyone.
    """
    kwargs = _assemble_kwargs(
        patient_factory, tumor_factory, diagnose_factory,
        required_kwargs=required_kwargs
    )
    reversed_url = urls.reverse(url_name, kwargs=kwargs)
    response = client.get(reversed_url)
    assert response.status_code == 200
