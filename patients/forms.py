from typing import Any, Dict

import pandas
from django import forms
from django.core.exceptions import ValidationError
from django.forms import widgets

from core.loggers import FormLoggerMixin

from .ioports import compute_hash
from .models import Diagnose, Institution, Patient, Tumor


class PatientForm(FormLoggerMixin, forms.ModelForm):
    """Form to create and edit patients, based on their model definition."""
    class Meta:
        model = Patient
        fields = ["sex",
                  "diagnose_date",
                  "alcohol_abuse",
                  "nicotine_abuse",
                  "hpv_status",
                  "neck_dissection",
                  "tnm_edition",
                  "n_stage",
                  "m_stage"]
        widgets = {"sex": widgets.Select(attrs={"class": "select"}),
                   "diagnose_date": widgets.NumberInput(attrs={"class": "input",
                                                               "type": "date"}),
                   "alcohol_abuse": widgets.Select(choices=[(True, "yes"),
                                                            (False, "no"),
                                                            (None, "unknown")],
                                                   attrs={"class": "select"}),
                   "nicotine_abuse": widgets.Select(choices=[(True, "yes"),
                                                             (False, "no"),
                                                             (None, "unknown")],
                                                  attrs={"class": "select"}),
                   "hpv_status": widgets.Select(choices=[(True, "positive"),
                                                         (False, "negative"),
                                                         (None, "unknown")],
                                                attrs={"class": "select"}),
                   "neck_dissection": widgets.Select(choices=[(True, "yes"),
                                                              (False, "no"),
                                                              (None, "unknown")],
                                                     attrs={"class": "select"}),
                   "tnm_edition": widgets.NumberInput(attrs={"class": "input"}),
                   "n_stage": widgets.Select(attrs={"class": "select"}),
                   "m_stage": widgets.Select(attrs={"class": "select"})}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.user = user

    first_name = forms.CharField(
        widget=widgets.TextInput(attrs={"class": "input",
                                        "placeholder": "First name"}))  #:
    last_name = forms.CharField(
        widget=widgets.TextInput(attrs={"class": "input",
                                        "placeholder": "Last name"}))    #:
    birthday = forms.DateField(
        widget=widgets.NumberInput(attrs={"class": "input",
                                          "type": "date"}))  #:
    check_for_duplicate = forms.BooleanField(
        widget=widgets.HiddenInput(),
        required=False)


    def save(self, commit=True):
        """Compute hashed ID and age from name, birthday and diagnose date."""
        patient = super(PatientForm, self).save(commit=False)

        patient.hash_value = self.cleaned_data["hash_value"]
        patient.age = self._compute_age()
        patient.institution = self.user.institution

        if commit:
            patient.save()

        return patient


    def clean(self):
        """Override superclass clean method to raise a ``ValidationError`` when
        a duplicate identifier is found."""
        cleaned_data = super(PatientForm, self).clean()
        unique_hash, cleaned_data = self._get_identifier(cleaned_data)

        if cleaned_data["check_for_duplicate"]:
            try:
                prev_patient_hash = Patient.objects.get(hash_value=unique_hash)
                msg = ("Hash value already in database. Entered patient might "
                       "be duplicate.")
                self.logger.warning(msg)
                raise forms.ValidationError(msg)

            # iff the above does not throw an exception, one can proceed
            except Patient.DoesNotExist:
                pass

        cleaned_data["hash_value"] = unique_hash
        return cleaned_data


    def _compute_age(self):
        """Compute age of patient at diagnose/admission."""
        bd = self.cleaned_data["birthday"]
        dd = self.cleaned_data["diagnose_date"]
        age = dd.year - bd.year

        if (dd.month < bd.month) or (dd.month == bd.month and dd.day < bd.day):
            age -= 1

        self.cleaned_data.pop("birthday")
        return age


    def _get_identifier(self, cleaned_data):
        """Compute the hashed undique identifier from fields that are of
        provacy concern."""
        hash_value = compute_hash(cleaned_data["first_name"],
                                  cleaned_data["last_name"],
                                  cleaned_data["birthday"])
        cleaned_data.pop("first_name")
        cleaned_data.pop("last_name")
        return hash_value, cleaned_data


class TumorForm(FormLoggerMixin, forms.ModelForm):
    """Form to create and edit tumors, based on their model definition."""
    class Meta:
        model = Tumor
        fields = ["t_stage",
                  "stage_prefix",
                  "subsite",
                  "central",
                  "extension",
                  "volume"]
        widgets = {
            "t_stage": forms.Select(attrs={"class": "select"}),
            "stage_prefix": forms.Select(attrs={"class": "select"}),
            "subsite": forms.Select(attrs={"class": "select shorten"}),
            "central": forms.CheckboxInput(attrs={"class": "checkbox"}),
            "extension": forms.CheckboxInput(attrs={"class": "checkbox"}),
            "volume": forms.NumberInput(attrs={"class": "input",
                                               "min": 0.0}),
        }

    def clean_volume(self):
        """Process the input for volume size."""
        volume = self.cleaned_data["volume"]
        if volume is not None and volume < 0.:
            raise ValidationError("volume must be a positive number.")
        return volume


    def save(self, commit=True):
        """Save tumor to existing patient."""
        tumor = super(TumorForm, self).save(commit=False)

        if commit:
            tumor.save()

        return tumor


class DiagnoseForm(FormLoggerMixin, forms.ModelForm):
    """Form to create and edit diagnoses, based on their model definition."""
    class Meta:
        model = Diagnose
        fields = ["diagnose_date",
                  "modality",
                  "side",]

        widgets = {"diagnose_date": forms.NumberInput(attrs={"class": "input is-small",
                                                             "type": "date"}),
                   "modality": forms.Select(attrs={"class": "select is-small"}),
                   "side": forms.Select(attrs={"class": "select is-small"})}

        for lnl in Diagnose.LNLs:
            fields.append(lnl)
            widgets[lnl] = forms.Select(choices=[(True, "pos"),
                                                 (False, "neg"),
                                                 (None, "???")],
                                        attrs={"class": "select"})

    def save(self, commit=True):
        """Save diagnose to existing patient."""
        diagnose = super(DiagnoseForm, self).save(commit=False)

        if diagnose.Ia or diagnose.Ib:
            diagnose.I = True

        if diagnose.IIa or diagnose.IIb:
            diagnose.II = True

        if commit:
            diagnose.save()

        return diagnose


class DataFileForm(FormLoggerMixin, forms.Form):
    """Accept and process a CSV file that can then be parsed to batch-create a
    number of patients at once."""
    data_file = forms.FileField(
        widget=forms.widgets.FileInput(attrs={"class": "file-input"})
    )

    def clean(self) -> Dict[str, Any]:
        """Cleaning method that makes sure the uploaded data is in fact a CSV
        file and can be parsed by ``pandas`` into a :class:`pandas.DataFrame`."""
        cleaned_data = super(DataFileForm, self).clean()
        suffix = cleaned_data["data_file"].name.split(".")[-1]
        if suffix != "csv":
            msg = "Uploaded file is not a CSV table."
            self.logger.warning(msg)
            raise ValidationError(msg)

        try:
            data_frame = pandas.read_csv(cleaned_data["data_file"],
                                         header=[0,1,2],
                                         skip_blank_lines=True,
                                         infer_datetime_format=True)
        except:
            msg = ("Error while parsing CSV table.")
            self.logger.error(msg)
            raise forms.ValidationError(
                msg + " Make sure format is as specified"
            )

        cleaned_data["data_frame"] = data_frame
        return cleaned_data


class InsitutionForm(FormLoggerMixin, forms.Form):
    """Form for creating an institution."""
    class Meta:
        model = Institution
