"""
Forms used in the `riskpredictor` app.

The first form, the `InferenceResultForm`, is used to create a new
`models.InferenceResult` and makes sure that the user enters a valid git repository
and revision.
"""
from typing import Any

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator
from django.forms import ValidationError, widgets
from dvc.api import DVCFileSystem
from dvc.scm import CloneError, RevError
from lyscripts.predict.utils import complete_pattern

from lyprox import loggers
from lyprox.dataexplorer.forms import ThreeWayToggle, trio_to_bool
from lyprox.riskpredictor.models import InferenceResult


class RangeInput(widgets.NumberInput):
    input_type = "range"


class InferenceResultForm(loggers.FormLoggerMixin, forms.ModelForm):
    """Form for creating a new `InferenceResult` instance."""

    class Meta:
        model = InferenceResult
        fields = [
            "repo_name",
            "ref",
            "graph_config_path",
            "model_config_path",
            "distributions_config_path",
            "num_samples",
        ]
        widgets = {
            "ref": widgets.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. `main`, commit hash, or tag name",
            }),
            "graph_config_path": widgets.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. `graph.ly.yaml`",
            }),
            "model_config_path": widgets.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. `model.ly.yaml`",
            }),
            "distributions_config_path": widgets.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. `graph.ly.yaml`",
            }),
            "num_samples": widgets.NumberInput(attrs={
                "class": "input",
                "placeholder": "e.g. 100",
            }),
        }

    def clean(self) -> dict[str, Any]:
        """Check all the fields for validity."""
        cleaned_data = super().clean()
        repo_name = cleaned_data["repo_name"]
        repo_url = f"https://github.com/{repo_name}"
        ref = cleaned_data["ref"]
        graph_config_path = cleaned_data["graph_config_path"]
        model_config_path = cleaned_data["model_config_path"]
        distributions_config_path = cleaned_data["distributions_config_path"]

        try:
            fs = DVCFileSystem(url=repo_url, rev=ref)

            if not fs.isfile(graph_config_path):
                self.add_error(
                    field="graph_config_path",
                    error=ValidationError("Not a valid path to the graph config."),
                )
            if not fs.isfile(model_config_path):
                self.add_error(
                    field="model_config_path",
                    error=ValidationError("Not a valid path to the model config."),
                )
            if not fs.isfile(distributions_config_path):
                self.add_error(
                    field="distributions_config_path",
                    error=ValidationError("Not a valid path to the distributions."),
                )
        except CloneError as _e:
            self.add_error(
                field="repo_name",
                error=ValidationError("Not an existing GitHub repository."),
            )
        except RevError as _e:
            self.add_error(
                field="ref",
                error=ValidationError("Not a valid git ref."),
            )

        return cleaned_data


class DashboardForm(forms.Form):
    """Form for the dashboard page."""
    is_submitted = forms.BooleanField(
        required=True, initial=True, widget=forms.HiddenInput
    )
    """Whether the form has been submitted via the button or not."""

    def __init__(self, *args, inference_result: InferenceResult = None, **kwargs):
        super().__init__(*args, **kwargs)

        if inference_result is not None:
            self.inference_result = inference_result
            self.add_lnl_fields(self.inference_result)
            self.add_t_stage_field(self.inference_result)
            self.add_sens_spec_fields()

            if self.inference_result.is_midline:
                self.add_midline_field()


    def add_lnl_fields(self, inference_result: InferenceResult):
        """Add the fields for the lymph node levels defined in the trained model."""
        for lnl in inference_result.lnls:
            self.fields[f"ipsi_{lnl}"] = ThreeWayToggle(initial=-1)

            if inference_result.is_bilateral:
                self.fields[f"contra_{lnl}"] = ThreeWayToggle(initial=-1)


    def add_t_stage_field(self, inference_result: InferenceResult):
        """Add the field for the T stage with the choices being defined in the model."""
        self.fields["t_stage"] = forms.ChoiceField(
            choices=[(t, t) for t in inference_result.t_stages],
            initial=inference_result.t_stages[0],
        )


    def add_sens_spec_fields(self, step: float = 0.01):
        """Add the fields for the sensitivity and specificity."""
        self.fields["sensitivity"] = forms.FloatField(
            min_value=0.5, max_value=1, initial=0.8,
            widget=RangeInput(attrs={
                "class": "tag slider is-fullwidth",
                "min": "0.5",
                "max": "1",
                "step": f"{step:.2f}",
            }),
            validators=[
                MinValueValidator(0.5, "Sensitivity below 0.5 makes no sense"),
                MaxValueValidator(1, "Sensitivity above 1 makes no sense"),
            ],
        )
        self.fields["specificity"] = forms.FloatField(
            min_value=0.5, max_value=1, initial=0.8,
            widget=RangeInput(attrs={
                "class": "tag slider is-fullwidth",
                "min": "0.5",
                "max": "1",
                "step": f"{step:.2f}",
            }),
            validators=[
                MinValueValidator(0.5, "Specificty below 0.5 makes no sense"),
                MaxValueValidator(1, "Specificty above 1 makes no sense"),
            ]
        )


    def add_midline_field(self):
        """Add the field for the midline status."""
        self.fields["midline_extension"] = ThreeWayToggle(
            label=None,
            tooltip="Does the tumor cross the mid-sagittal line?",
            choices=[(1, "plus"), (0, "ban"), (-1, "minus")],
            initial=-1,
        )


    def clean_midline_extension(self) -> bool:
        """For now, the midline extension cannot be unknown (value of 0)."""
        midline_extension = self.cleaned_data["midline_extension"]
        if midline_extension == 0:
            raise ValidationError("Midline extension cannot be unknown.")
        return midline_extension


    def clean(self) -> dict[str, Any]:
        """Transform three-way toggles to booleans."""
        cleaned_data = super().clean()

        for field_name, field_value in cleaned_data.items():
            cleaned_data[field_name] = trio_to_bool(field_value)

        diagnosis = {}
        for side in ["ipsi", "contra"]:
            diagnosis[side] = {}
            for lnl in self.inference_result.lnls:
                if (key := f"{side}_{lnl}") not in cleaned_data:
                    continue
                diagnosis[side][lnl] = cleaned_data.pop(key)

        cleaned_data["diagnosis"] = complete_pattern(
            diagnosis, self.inference_result.lnls
        )
        return cleaned_data
