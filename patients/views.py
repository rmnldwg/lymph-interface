import logging
import time
from pathlib import Path
from typing import Any, Dict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.shortcuts import render
from django.urls.base import reverse
from django.views import generic

from dashboard import query
from dashboard.forms import DashboardForm

logger = logging.getLogger(__name__)

from core.loggers import ViewLoggerMixin

from .filters import PatientFilter
from .forms import DataFileForm, DiagnoseForm, PatientForm, TumorForm
from .ioports import ParsingError, export_to_pandas, import_from_pandas
from .mixins import InstitutionCheckObjectMixin, InstitutionCheckPatientMixin
from .models import Diagnose, Patient, Tumor


# PATIENT related views
class PatientListView(ViewLoggerMixin, generic.ListView):
    """Renders a list of all patients in the database showing basic information
    and links to the individual entries. Depending from where this view is
    called, the list is filterable.
    """
    model = Patient
    form_class = DashboardForm
    filterset_class = PatientFilter
    template_name = "patients/list.html"  #:
    context_object_name = "patient_list"  #:
    action = "show_patient_list"  #:
    is_filterable = True
    queryset_pk_list = []

    def get_queryset(self) -> QuerySet[Patient]:
        """Add ability to filter queryset via FilterSets to generic ListView."""
        queryset = super().get_queryset()
        start_querying = time.perf_counter()

        if not self.request.user.is_authenticated:
            queryset = queryset.filter(institution__is_hidden=False)

        self.filterset = self.filterset_class(
            self.request.GET or None, queryset
        )
        self.form = self.form_class(
            self.request.GET or None, user=self.request.user
        )

        if self.filterset.is_valid():
            queryset = self.filterset.qs.distinct()

        if self.form.is_valid():
            self.is_filterable = False
            queryset = query.patient_specific(
                patient_queryset=queryset, **self.form.cleaned_data
            )
            queryset = query.tumor_specific(
                patient_queryset=queryset, **self.form.cleaned_data
            )
            queryset, combined_involvement = query.diagnose_specific(
                patient_queryset=queryset, **self.form.cleaned_data
            )
            queryset, _ = query.n_zero_specific(
                patient_queryset=queryset,
                combined_involvement=combined_involvement,
                n_status=self.form.cleaned_data['n_status']
            )

        self.queryset_pk_list = list(queryset.values_list("pk", flat=True))
        self.logger.debug(",".join(str(pk) for pk in self.queryset_pk_list))

        end_querying = time.perf_counter()
        self.logger.info(
            f'Querying finished in {end_querying - start_querying:.3f} seconds'
        )
        return queryset


    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add FilterSet to context for displaying filter form."""
        context = super().get_context_data(**kwargs)

        context["queryset_pk_list"] = self.queryset_pk_list
        context["is_filterable"] = self.is_filterable
        if self.is_filterable:
            context["filterset"] = self.filterset

        return context


class PatientDetailView(generic.DetailView):
    """Show details of a particular patient."""
    model = Patient
    template_name = "patients/patient_detail.html"  #:
    action = "show_patient_detail"  #:


class CreatePatientView(ViewLoggerMixin,
                        LoginRequiredMixin,
                        generic.CreateView):
    """View used to create a new patient entry in the database."""
    model = Patient
    form_class = PatientForm
    template_name = "patients/patient_form.html"  #:
    action = "create_patient"  #:

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add ``action`` to context for rendering purposes."""
        context = super().get_context_data(**kwargs)
        context["action"] = self.action
        return context

    def get_form_kwargs(self) -> Dict[str, Any]:
        """Pass user to form, so that a newly created patient can be assigned
        to the same institution as the user who created them."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class UpdatePatientView(ViewLoggerMixin,
                        LoginRequiredMixin,
                        InstitutionCheckPatientMixin,
                        generic.UpdateView):
    """Update a given patient's information."""
    model = Patient
    form_class = PatientForm
    template_name = "patients/patient_form.html"  #:
    action = "edit_patient"  #:

    def get_success_url(self) -> str:
        """When successfully edited, redirect to that patient's
        :class:`PatientDetailView`"""
        return reverse("patients:detail", kwargs=self.kwargs)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add ``action`` to context for rendering purposes."""
        context = super().get_context_data(**kwargs)
        context["action"] = self.action
        return context

    def get_form_kwargs(self) -> Dict[str, Any]:
        """Pass current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class DeletePatientView(ViewLoggerMixin,
                        LoginRequiredMixin,
                        InstitutionCheckPatientMixin,
                        generic.DeleteView):
    """Remove this patient from the database."""
    model = Patient
    template_name = "patients/patient_delete.html"  #:
    success_url = "/patients"  #:
    action = "delete_patient"  #:


@login_required
def upload_patients(request):
    """View to load many patients at once from a CSV file using pandas. This
    requires the CSV file to be formatted in a certain way."""
    if request.method == "POST":
        form = DataFileForm(request.POST, request.FILES)

        # custom validator creates pandas DataFrame from uploaded CSV
        if form.is_valid():
            data_frame = form.cleaned_data["data_frame"]
            # creating patients from the resulting pandas DataFrame
            try:
                num_new, num_skipped = import_from_pandas(data_frame, request.user)
            except ParsingError as pe:
                logger.error(pe)
                form = DataFileForm()
                context = {"upload_success": False,
                           "form": form,
                           "error": pe}
                return render(request, "patients/upload.html", context)

            context = {"upload_success": True,
                       "num_new": num_new,
                       "num_skipped": num_skipped}
            return render(request, "patients/upload.html", context)

    else:
        form = DataFileForm()

    context = {"upload_succes": False, "form": form}
    return render(request, "patients/upload.html", context)


def generate_and_download_csv(request):
    """
    Allow user to generate a CSV table from the current database and
    download it. The returned CSV table has exactly the structure that is
    necessary to upload a batch of patients.

    Only logged in users can download the entire database. Unauthenticated
    users can only download a CSV table of datasets that are not hidden.
    """

    # NOTE: This is only possible as long as the static files are served from
    #   the same directory as the root directory of the django app.
    # download_folder = settings.MEDIA_ROOT / "downloads"
    download_file_path = settings.DOWNLOADS_ROOT / "latest.csv"
    user = request.user
    context = {}

    if request.method == "POST":
        if user.is_authenticated:
            queryset = Patient.objects.all()
        else:
            queryset = Patient.objects.all().filter(institution__is_hidden=False)

        if len(queryset) == 0:
            context["generate_success"] = False
            context["error"] = "List of exportable patients is empty"
            return render(request, "patients/download.html", context)

        try:
            patient_df = export_to_pandas(queryset)
            patient_df.to_csv(download_file_path, index=False)
            logger.info("Successfully generated and saved database as CSV.")
            context["generate_success"] = True

        except FileNotFoundError:
            msg = ("Download folder is missing or can't be accessed.")
            logger.error(msg)
            context["generate_success"] = False
            context["error"] = msg

        except Exception as err:
            logger.error(err)
            context["generate_success"] = False
            context["error"] = err

    context["download_available"] = Path(download_file_path).is_file()
    return render(request, "patients/download.html", context)


# TUMOR related views
class CreateTumorView(ViewLoggerMixin,
                      LoginRequiredMixin,
                      InstitutionCheckObjectMixin,
                      generic.CreateView):
    """Create a tumor and add it to a given patient."""
    model = Tumor
    form_class = TumorForm
    template_name = "patients/patient_detail.html"  #:
    action = "create_tumor"  #:

    def form_valid(self, form: TumorForm) -> HttpResponse:
        """After form validation, add the tumor to the given patient."""
        # assign tumor to current patient
        tumor = form.save(commit=False)
        tumor.patient = Patient.objects.get(**self.kwargs)

        return super(CreateTumorView, self).form_valid(form)

    def get_success_url(self) -> str:
        """After successfull creation, redirect to the patient's detail view
        that also contains info about this tumor."""
        return reverse("patients:detail", kwargs=self.kwargs)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add this tumor's patient, the patient's tumor and diagnoses, as well
        as the currently performed action to the context dictionary."""
        context = super().get_context_data(**kwargs)
        context["action"] = self.action

        patient = Patient.objects.get(**self.kwargs)
        context["patient"] = patient

        tumors = Tumor.objects.all().filter(patient=patient)
        context["tumors"] = tumors

        diagnoses = Diagnose.objects.all().filter(patient=patient)
        context["diagnoses"] = diagnoses

        return context


class UpdateTumorView(ViewLoggerMixin,
                      LoginRequiredMixin,
                      InstitutionCheckObjectMixin,
                      generic.UpdateView):
    """Update specifics of a patient's tumor."""
    model = Tumor
    form_class = TumorForm
    template_name = "patients/patient_detail.html"  #:
    action = "update_tumor"  #:

    def get_object(self):
        """Get tumor by ``PK``."""
        return Tumor.objects.get(pk=self.kwargs["tumor_pk"])

    def get_success_url(self) -> str:
        """After successfully updating the tumor, redirect to patient's detail
        view."""
        return reverse("patients:detail",
                       kwargs={"pk": self.kwargs["pk"]})

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add this tumor's patient, the patient's tumor and diagnoses, as well
        as the currently performed action to the context dictionary."""
        context = super().get_context_data(**kwargs)
        context["action"] = self.action

        patient = Patient.objects.get(pk=self.kwargs["pk"])
        context["patient"] = patient

        tumors = Tumor.objects.all().filter(
            patient=patient
        ).exclude(
            pk=self.kwargs["tumor_pk"]
        )
        context["tumors"] = tumors

        diagnoses = Diagnose.objects.all().filter(patient=patient)
        context["diagnoses"] = diagnoses

        return context


class DeleteTumorView(ViewLoggerMixin,
                      LoginRequiredMixin,
                      InstitutionCheckObjectMixin,
                      generic.DeleteView):
    """Delete a patient's tumor."""
    model = Tumor
    template_name = "patients/patient_detail.html"
    action = "delete_tumor"

    def get_object(self):
        """Get tumor by ``PK``."""
        return Tumor.objects.get(pk=self.kwargs["tumor_pk"])

    def get_success_url(self) -> str:
        """After successfully updating the tumor, redirect to patient's detail
        view."""
        return reverse("patients:detail", kwargs={"pk": self.kwargs["pk"]})

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add this tumor's patient, the patient's tumor and diagnoses, as well
        as the currently performed action to the context dictionary."""
        context = super().get_context_data(**kwargs)
        context["action"] = self.action

        patient = Patient.objects.get(pk=self.kwargs["pk"])
        context["patient"] = patient

        tumors = Tumor.objects.all().filter(
            patient=patient
        ).exclude(
            pk=self.kwargs["tumor_pk"]
        )
        context["tumors"] = tumors

        diagnoses = Diagnose.objects.all().filter(patient=patient)
        context["diagnoses"] = diagnoses

        return context


# DIAGNOSE related views
class CreateDiagnoseView(ViewLoggerMixin,
                         LoginRequiredMixin,
                         InstitutionCheckObjectMixin,
                         generic.CreateView):
    """Add a diagnose for a patient's lymphatic system."""
    model = Diagnose
    form_class = DiagnoseForm
    template_name = "patients/patient_detail.html"  #:
    action = "create_diagnose"  #:

    def form_valid(self, form: DiagnoseForm) -> HttpResponse:
        """As with the tumor, add the diagnose to the already existing patient
        after the form was validated."""
        diagnose = form.save(commit=False)
        diagnose.patient = Patient.objects.get(**self.kwargs)
        return super(CreateDiagnoseView, self).form_valid(form)

    def get_success_url(self) -> str:
        """After successfully updating the diagnose, redirect to patient's
        detail view."""
        return reverse("patients:detail", kwargs=self.kwargs)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add this diagnose's patient, the patient's tumor and diagnoses, as
        well as the currently performed action to the context dictionary."""
        context = super().get_context_data(**kwargs)
        context["action"] = self.action

        patient = Patient.objects.get(**self.kwargs)
        context["patient"] = patient

        tumors = Tumor.objects.all().filter(patient=patient)
        context["tumors"] = tumors

        diagnoses = Diagnose.objects.all().filter(patient=patient)
        context["diagnoses"] = diagnoses

        return context


class UpdateDiagnoseView(ViewLoggerMixin,
                         LoginRequiredMixin,
                         InstitutionCheckObjectMixin,
                         generic.UpdateView):
    """Change a patient's diagnose."""
    model = Diagnose
    form_class = DiagnoseForm
    template_name = "patients/patient_detail.html"  #:
    action = "update_diagnose"  #:

    def get_object(self):
        """Get diagnose by ``PK``."""
        return Diagnose.objects.get(pk=self.kwargs["diagnose_pk"])

    def get_success_url(self) -> str:
        """After successfully updating the diagnose, redirect to patient's
        detail view."""
        return reverse("patients:detail",
                       kwargs={"pk": self.kwargs["pk"]})

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add this diagnose's patient, the patient's tumor and diagnoses, as
        well as the currently performed action to the context dictionary."""
        context = super().get_context_data(**kwargs)
        context["action"] = self.action

        patient = Patient.objects.get(pk=self.kwargs["pk"])
        context["patient"] = patient

        tumors = Tumor.objects.all().filter(patient=patient)
        context["tumors"] = tumors

        diagnoses = Diagnose.objects.all().filter(
            patient=patient
        ).exclude(
            pk=self.kwargs["diagnose_pk"]
        )
        context["diagnoses"] = diagnoses

        return context


class DeleteDiagnoseView(ViewLoggerMixin,
                         LoginRequiredMixin,
                         InstitutionCheckObjectMixin,
                         generic.DeleteView):
    """Remove a particular diagnose frm a patient's entry."""
    model = Diagnose
    template_name = "patients/patient_detail.html"  #:
    action = "delete_diagnose"  #:

    def get_object(self):
        """Get diagnose by ``PK``."""
        return Diagnose.objects.get(pk=self.kwargs["diagnose_pk"])

    def get_success_url(self) -> str:
        """After successfully updating the diagnose, redirect to patient's
        detail view."""
        return reverse("patients:detail", kwargs={"pk": self.kwargs["pk"]})

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add this diagnose's patient, the patient's tumor and diagnoses, as
        well as the currently performed action to the context dictionary."""
        context = super().get_context_data(**kwargs)
        context["action"] = self.action

        patient = Patient.objects.get(pk=self.kwargs["pk"])
        context["patient"] = patient

        tumors = Tumor.objects.all().filter(patient=patient)
        context["tumors"] = tumors

        diagnoses = Diagnose.objects.all().filter(
            patient=patient
        ).exclude(
            pk=self.kwargs["diagnose_pk"]
        )
        context["diagnoses"] = diagnoses

        return context
