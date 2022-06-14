"""
This module defines how patient related models work and how they interact with each
other. Currently, four models are implemented: The `Dataset`, `Patient`, `Tumor`
and the `Diagnose`. A `Dataset` groups `Patient` entries and associates them with an
`Institution`, while also providing methods for importing and exporting from and to CSV
file.

A `Patient` holds demographic and relational information about each recorded patient.
The respective entry can have multiple `Tumor` and `Diagnose` entries associated with
it, which is defined by the ``django.db.models.ForeignKey`` attribute in the `Tumor`
and `Diagnose` class.

There are also custom methods implemented, making sure that e.g. the diagnosis
of a sublevel (lets say ``Ia``) is consistent with the diagnosis of the
respective superlevel (in that case ``I``).
"""
# pylint: disable=no-member
# pylint: disable=logging-fstring-interpolation

from collections import namedtuple
from io import BytesIO
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.files import File
from django.core.validators import FileExtensionValidator
from django.db import models
from django.forms import ValidationError
from django.urls import reverse
from django.utils import timezone

import patients.ioports as ioports
from core.loggers import ModelLoggerMixin

from .fields import DuplicateFileError, FileFieldWithHash, RobustDateField


def directory_(used_for: str, instance):
    """
    Function that compiles and returns the path to where uploaded or exported CSV
    files will be stored. It also creates the respective folder and deletes any
    existing iles with the same name if necessary.
    """
    media_root = Path(settings.MEDIA_ROOT)
    folder_path = media_root.joinpath(used_for)
    folder_path.mkdir(parents=True, exist_ok=True)
    file_path = folder_path.joinpath(f"{instance}.csv")
    file_path.unlink(missing_ok=True)
    return f"{used_for}/{instance}.csv"

def directory_for_uploads(instance, _filename) -> str:
    """Calls `directory_` for 'uploads'."""
    return directory_(used_for="uploads", instance=instance)

def directory_for_exports(instance, _filename) -> str:
    """Calls `directory_` for 'exports'."""
    return directory_(used_for="exports", instance=instance)


class Dataset(ModelLoggerMixin, models.Model):
    """
    This model represents a collection of patients that have been added to the
    database together. E.g., via uploading a CSV file where each row represents a
    patient. But also patients added via the interface one by one should be associated
    to a dataset.

    The dataset model's functionality includes an interface between the database and
    CSV files. As mentioned, a user should be able to batch-import patients via a
    specifically formatted CSV table. But one should also be able to export all
    patients of a dataset to a CSV file.
    """
    name = models.CharField(max_length=100)
    """The name of the dataset. Should not include any dates or the institution."""
    description = models.TextField()
    """A brief description of the dataset."""
    create_date = models.DateField(default=timezone.now)
    """Date when the dataset was uploaded."""
    is_public = models.BooleanField(default=False)
    """Should this dataset be visible to non-authenticated users?"""
    is_locked = models.BooleanField(default=False)
    """This indicates that one is done adding patients to this dataset and it should
    be prohibited to change the dataset or any of its associated entries when this is
    set to ``True``."""

    upload_csv = FileFieldWithHash(
        upload_to=directory_for_uploads,
        validators=[FileExtensionValidator(allowed_extensions=["csv"])],
        null=True, blank=True,
    )
    """The custom ``FileField`` that holds the uploaded CSV file."""
    export_csv = FileFieldWithHash(
        upload_to=directory_for_exports,
        validators=[FileExtensionValidator(allowed_extensions=["csv"])],
        null=True, blank=True,
    )
    """The custom ``FileField`` that holds the exported CSV file."""

    def __str__(self) -> str:
        year = self.create_date.strftime("%Y")
        return f"{year}-{self.name}"

    def _validate_unique(
        self,
        for_fieldname: str,
        do_delete: bool = False,
        do_warn: bool = True,
        do_raise: bool = True,
    ):
        """
        Make sure no other `Dataset` holds the same file in one of their ``FileFields``
        or the uploaded file is already stored on disk.

        With the argument `do_delete` one can control if the file should be deleted
        (and with `do_warn` if that deletion should trigger a warning through the
        logger) when a duplicate was found and with `do_raise` whether a
        `DuplicateFileError` should ultimately be raised.
        """
        all_except_self = Dataset.objects.all().exclude(pk=self.pk)
        for dataset in all_except_self:
            self_filefield = getattr(self, for_fieldname)
            ds_filefield = getattr(dataset, for_fieldname)
            try:
                if self_filefield.md5_hash == ds_filefield.md5_hash:
                    if do_delete:
                        getattr(self, for_fieldname).delete(save=False)
                        if do_warn:
                            self.logger.warning(
                                f"The {for_fieldname} of {self} was deleted because "
                                f"it is a duplicate of {dataset}"
                            )
                    if do_raise:
                        raise DuplicateFileError(
                            "This file is already associated "
                            f"with the dataset {dataset}"
                        )
            except ValueError:
                # This is necessary because if no file has been assigned to the
                # respective FileField, the ``_require_file`` method of the FieldFile
                # will raise a ValueError, in which case we can just skip that one.
                continue

    def validate_unique(self, exclude=None) -> None:
        """Validate uniqueness of the uploaded CSV file."""
        try:
            self._validate_unique(
                for_fieldname="upload_csv", do_delete=False, do_raise=True
            )
        except DuplicateFileError as df_err:
            raise ValidationError({
                "upload_csv": "File has already been uploaded."
            }) from df_err
        super().validate_unique(exclude)

    def lock(self):
        """Set the field `is_locked` to ``True``"""
        self.is_locked = True
        self.save(override=True)

    def unlock(self):
        """
        Set `is_locked` to ``False``, allowing the dataset and its patients to be
        edited again.
        """
        self.is_locked = False
        self.save()

    def save(self, *args, override=False, **kwargs):
        """
        Add uniqueness checks to save method, as well as blocking any changes when
        the dataset is locked (and `override` is not set to ``True``).
        """
        if self.is_locked and not override:
            self.logger.warning("Editing a locked dataset is prohibited.")
            return

        self._validate_unique(
            for_fieldname="upload_csv", do_delete=True, do_warn=True, do_raise=False
        )
        self._validate_unique(
            for_fieldname="export_csv", do_delete=True, do_warn=True, do_raise=False
        )
        return super().save(*args, **kwargs)

    def get_pandas_from_db(self):
        """
        Generate a `pandas.DataFrame` for all patients associated with this dataset
        using the `ioports` module and then return that.
        """
        patients = Patient.objects.all().filter(dataset=self)
        return ioports.export_to_pandas(patients)

    def get_pandas_from_csv(self):
        """
        Simply extract a `pandas.DataFrame` from an uploaded CSV.
        """
        if not self.upload_csv.readable() or self.upload_csv.mode != "rb":
            self.upload_csv.open(mode="rb")

        file_content = self.upload_csv.read()
        binary_buffer = BytesIO(file_content)
        self.upload_csv.close()

        table = pd.read_csv(binary_buffer, header=[0,1,2])
        return table

    def export_db_to_csv(self):
        """
        First, call the `get_pandas_from_db` method to get a `pandas.DataFrame` of
        patients from the database. Then, save that table in the form of a CSV file
        to disk and associate it with the `fields.FileFieldWithHash` called
        `export_csv`.
        """
        table = self.get_pandas_from_db()
        write_buffer = BytesIO()
        table.to_csv(write_buffer, index=None)
        file = File(write_buffer)
        self.export_csv.save("this-has-no-effect", file, save=True)

    def import_upload_csv_to_db(self):
        """
        Import an uploaded CSV into the database using the `ioports` module. Lock the
        dataset right afterwards to prevent editing the uploaded patients.
        """


class Patient(ModelLoggerMixin, models.Model):
    """
    The representation of a patient in the database. It contains some
    demographic information, as well as patient-specific characteristics that
    are important in the context of cancer, e.g. HPV status.

    This model also ties together the information about the patient's tumor(s)
    and the lymphatic progression pattern of that patient in the form of a
    `Diagnose` model.
    """
    hash_value = models.CharField(max_length=200, unique=True)
    """Unique ID computed from sensitive info upon patient creation."""

    sex = models.CharField(max_length=10, choices=[("female", "female"),
                                                   ("male"  , "male"  )])
    age = models.IntegerField()
    diagnose_date = RobustDateField()
    """Date of histological confirmation with a squamous cell carcinoma."""

    alcohol_abuse = models.BooleanField(blank=True, null=True)
    """Was the patient a drinker?"""

    nicotine_abuse = models.BooleanField(blank=True, null=True)
    """Was the patient a smoker"""

    hpv_status = models.BooleanField(blank=True, null=True)
    """Was the patient HPV positive (``True``) or negative (``False``)?"""

    neck_dissection = models.BooleanField(blank=True, null=True)
    """Did the patient undergo (radical) neck dissection?"""

    tnm_edition = models.PositiveSmallIntegerField(default=8)
    """The edition of the TNM staging system that was used."""

    stage_prefix = models.CharField(
        max_length=1, choices=[("c", "c"), ("p", "p")], default='c'
    )
    """T-stage prefix: 'c' for 'clinical' and 'p' for 'pathological'."""

    class T_stages(models.IntegerChoices):
        """Defines the possible T-stages as choice class."""
        T1 = 1, "T1"
        T2 = 2, "T2"
        T3 = 3, "T3"
        T4 = 4, "T4"

    t_stage = models.PositiveSmallIntegerField(
        choices=T_stages.choices, default=0
    )
    """Stage of the primary tumor. Categorized the tumor by size and
    infiltration of tissue types."""

    class N_stages(models.IntegerChoices):
        """Defines the possible N-stages as choice class."""
        N0 = 0, "N0"
        N1 = 1, "N1"
        N2 = 2, "N2"
        N3 = 3, "N3"

    n_stage = models.PositiveSmallIntegerField(choices=N_stages.choices)
    """Categorizes the extend of regional metastases."""

    class M_stages(models.IntegerChoices):
        """Defines the possible M-stages as choice class."""
        M0 = 0, "M0"
        M1 = 1, "M1"
        MX = 2, "MX"

    m_stage = models.PositiveSmallIntegerField(choices=M_stages.choices)
    """Indicates whether or not there are distant metastases."""

    dataset = models.ForeignKey(to=Dataset, on_delete=models.CASCADE)
    """Every patient must belong to a dataset entry that manages importing, exporting
    as well as preventing edits that compromise the integrity of the dataset."""

    def __str__(self):
        """Report some patient specifics."""
        return (
            f"#{self.pk}: {self.sex} ({self.age}) at "
            f"{self.institution.shortname}"
        )

    def get_absolute_url(self):
        """Return the absolute URL for a particular patient."""
        return reverse("patients:detail", args=[self.pk])

    def get_tumors(self):
        """Return the primary tumor(s) of that patient."""
        tumors = Tumor.objects.all().filter(patient=self)
        return tumors

    def get_diagnoses(self):
        """Return the LNL diagnose(s) of the patient."""
        diagnoses = Diagnose.objects.all().filter(patient=self)
        return diagnoses

    def update_t_stage(self):
        """
        Update T-stage after new `Tumor` is added to `Patient`
        (gets called in `Tumor.save` method). Also updates the patient's
        stage prefix to that of the tumor with the highest T-category.
        """
        tumors = Tumor.objects.all().filter(patient=self)

        max_t_stage = 0
        stage_prefix = 'c'
        for tumor in tumors:
            if max_t_stage < tumor.t_stage:
                max_t_stage = tumor.t_stage
                stage_prefix = tumor.stage_prefix

        self.t_stage = max_t_stage
        self.stage_prefix = stage_prefix
        self.save()
        self.logger.debug(
            f"T-stage of patient {self} updated to "
            f"{self.get_stage_prefix_display()}{self.get_t_stage_display()}."
        )


class Tumor(ModelLoggerMixin, models.Model):
    """
    Model to describe a patient's tumor in detail. It is connected to a patient
    via a ``django.db.models.ForeignKey`` relation.
    """

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    """This defines the connection to the `Patient` model."""

    class Locations(models.TextChoices):
        """The primary tumor locations in the head and neck region."""
        ORAL_CAVITY = "oral cavity"
        OROPHARYNX  = "oropharynx"
        HYPOPHARYNX = "hypopharynx"
        LARYNX      = "larynx"

    location = models.CharField(max_length=20, choices=Locations.choices)
    """The tumor location."""

    SUBSITES = [
        ("oral cavity", (("C02.0", "dorsal surface of tongue"),
                         ("C02.1", "border of tongue"),
                         ("C02.2", "ventral surface of tongue"),
                         ("C02.3", "anterior two thirds of tongue"),
                         ("C02.4", "lingual tonsil"),
                         ("C02.8", "overlapping sites of tongue"),
                         ("C02.9", "tongue, nos"),

                         ("C03.0", "upper gum"),
                         ("C03.1", "lower gum"),
                         ("C03.9", "gum, nos"),

                         ("C04.0", "anterior floor of mouth"),
                         ("C04.1", "lateral floor of mouth"),
                         ("C04.8", "overlapping lesion of floor of mouth"),
                         ("C04.9", "floor of mouth, nos"),

                         ("C05.0", "hard palate"),
                         ("C05.1", "soft palate, nos"),
                         ("C05.2", "uvula"),
                         ("C05.8", "overlapping lesion of palate"),
                         ("C05.9", "palate, nos"),

                         ("C06.0", "cheeck mucosa"),
                         ("C06.1", "vestibule of mouth"),
                         ("C06.2", "retromolar area"),
                         ("C06.8", "overlapping lesion(s) of NOS parts of mouth"),
                         ("C06.9", "mouth, nos"),

                         ("C08.0", "submandibular gland"),
                         ("C08.1", "sublingual gland"),
                         ("C08.9", "salivary gland, nos"))
        ),
        ("oropharynx",  (("C01"  , "base of tongue, nos"),

                         ("C09.0", "tonsillar fossa"),
                         ("C09.1", "tonsillar pillar"),
                         ("C09.8", "overlapping lesion of tonsil"),
                         ("C09.9", "tonsil, nos"),

                         ("C10.0", "vallecula"),
                         ("C10.1", "anterior surface of epiglottis"),
                         ("C10.2", "lateral wall of oropharynx"),
                         ("C10.3", "posterior wall of oropharynx"),
                         ("C10.4", "branchial cleft"),
                         ("C10.8", "overlapping lesions of oropharynx"),
                         ("C10.9", "oropharynx, nos"),)
        ),
        ("hypopharynx", (("C12"  , "pyriform sinus"),

                         ("C13.0", "postcricoid region"),
                         ("C13.1", "hypopharyngeal aspect of aryepiglottic fold"),
                         ("C13.2", "posterior wall of hypopharynx"),
                         ("C13.8", "overlapping lesion of hypopharynx"),
                         ("C13.9", "hypopharynx, nos"),)
        ),
        ("larynx",      (("C32.0", "glottis"),
                         ("C32.1", "supraglottis"),
                         ("C32.2", "subglottis"),
                         ("C32.3", "laryngeal cartilage"),
                         ("C32.8", "overlapping lesion of larynx"),
                         ("C32.9", "larynx, nos"),)
        )
    ]
    """List of subsites with their ICD-10 code and respective description,
    grouped by location."""

    # NOTE: The ICD-10 codes `C01` and `C01.9` refer to the same subsite. `C01`
    # is correct, but for resilience, I also accept `C01.9` until I implement
    # my own ICD interface.
    SUBSITE_DICT = {
        "base":        ["C01"  , "C01.9"],
        "tonsil":      ["C09.0", "C09.1", "C09.8", "C09.9"],
        "rest_oro":    ["C10.0", "C10.1", "C10.2", "C10.3",
                        "C10.4", "C10.8", "C10.9"],
        "rest_hypo":   ["C12"  , "C12.9",
                        "C13.0", "C13.1", "C13.2", "C13.8", "C13.9"],
        "glottis":     ["C32.0"],
        "rest_larynx": ["C32.1", "C32.2", "C32.3", "C32.8", "C32.9"],
        "tongue":      ["C02.0", "C02.1", "C02.2", "C02.3", "C02.4", "C02.8",
                        "C02.9",],
        "gum_cheek":   ["C03.0", "C03.1", "C03.9", "C06.0", "C06.1", "C06.2",
                        "C06.8", "C06.9",],
        "mouth_floor": ["C04.0", "C04.1", "C04.8", "C04.9",],
        "palate":      ["C05.0", "C05.1", "C05.2", "C05.8", "C05.9",],
        "glands":      ["C08.0", "C08.1", "C08.9",],
    }
    SUBSITE_LIST = [icd for icd_list in SUBSITE_DICT.values() for icd in icd_list]

    subsite = models.CharField(max_length=10, choices=SUBSITES)
    """The subsite is a more granular categorization by the anatomical region
    of the head and neck where the primary tumor occurs in. It is usually
    encoded using the ICD-10 codes."""

    central = models.BooleanField(blank=True, null=True)
    """Is the tumor symmetric w.r.t. the patients mid-sagittal line?"""

    extension = models.BooleanField(blank=True, null=True)
    """Does the tumor cross the mid-sagittal line of the patient?"""

    volume = models.FloatField(blank=True, null=True)
    """Volume of the patient's tumor."""

    t_stage = models.PositiveSmallIntegerField(choices=Patient.T_stages.choices)
    """Stage of the primary tumor. Categorized the tumor by size and
    infiltration of tissue types."""

    stage_prefix = models.CharField(max_length=1, choices=[("c", "c"),
                                                           ("p", "p")])
    """T-stage prefix: 'c' for 'clinical' and 'p' for 'pathological'."""

    def __str__(self):
        """Report some main characteristics."""
        return f"#{self.pk}: T{self.t_stage} tumor of patient #{self.patient.pk}"

    def save(self, *args, **kwargs):
        """
        Before creating the database entry, determine the location of the
        tumor from the specified subsite and update the patient it is assigned
        to, to the correct T-stage.
        """
        # Automatically extract location from subsite
        subsite_dict = dict(self.SUBSITES)
        location_list = self.Locations.values

        found_location = False
        for loc in location_list:
            loc_subsites = [tpl[1] for tpl in subsite_dict[loc]]
            if self.get_subsite_display() in loc_subsites:
                self.location = loc
                found_location = True

        if not found_location:
            self.logger.warning(
                "Could not extract location for this tumor's "
                f"({self}) subsite ({self.get_subsite_display()})"
            )

        tmp_return = super(Tumor, self).save(*args, **kwargs)

        # call patient's `update_t_stage` method
        self.patient.update_t_stage()

        return tmp_return

    def delete(self, *args, **kwargs):
        """Upon deletion, update the patient's T-stage."""
        patient = self.patient
        tmp = super(Tumor, self).delete(*args, **kwargs)
        patient.update_t_stage()
        return tmp


Mod = namedtuple("Mod", "value label spec sens")

class Diagnose(ModelLoggerMixin, models.Model):
    """
    Model describing the diagnosis of one side of a patient's neck with
    regard to their lymphaitc metastatic involvement.
    """

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    """This defines the connection to the `Patient` model."""

    class MetaModality(type):
        """
        Meta class for providing the classmethod attributes to the
        `Modalities` class similar to what Django's enum types have.
        """
        def __init__(cls, classname, bases, classdict, *args, **kwargs):
            cls._mods = []
            for key, val in classdict.items():
                if (
                    not key.startswith("_")
                    and not callable(val)
                    and all([c.isupper() for c in key])
                ):
                    cls._mods.append(val)

            super().__init__(classname, bases, classdict, *args, **kwargs)

        def __len__(cls):
            return len(cls._mods)

        def __iter__(cls):
            cls._i = 0
            return cls

        def __next__(cls):
            if cls._i < len(cls):
                mod = cls._mods[cls._i]
                cls._i += 1
                return mod
            else:
                raise StopIteration

        @property
        def choices(cls):
            """Return list of tuples suitable for the
            ``django.db.models.ChoiceField``"""
            return [(mod.value, mod.label) for mod in cls._mods]

        @property
        def values(cls):
            """Database values the modality field can take on."""
            return [mod.value for mod in cls._mods]

        @property
        def labels(cls):
            """Human readable labels for the values of the modality field."""
            return [mod.label for mod in cls._mods]

        @property
        def spsn(cls):
            """Sensitiviy & specificity of the implemented modalities."""
            return [[mod.spec, mod.sens] for mod in cls._mods]

    class Modalities(metaclass=MetaModality):
        """
        Class that aims to replicate the functionality of ``TextChoices``
        from Django's enum types, but with the added functionality of storing
        the sensitivity & specificity of the respective modality.
        """
        CT   = Mod("CT" ,                  "CT" ,                    0.76, 0.81)
        MRI  = Mod("MRI",                  "MRI",                    0.63, 0.81)
        PET  = Mod("PET",                  "PET",                    0.86, 0.79)
        FNA  = Mod("FNA",                  "Fine Needle Aspiration", 0.98, 0.80)
        DC   = Mod("diagnostic_consensus", "Diagnostic Consensus"  , 0.86, 0.81)
        PATH = Mod("pathology",            "Pathology",              1.  , 1.  )
        PCT  = Mod("pCT",                  "Planning CT",            0.86, 0.81)

    modality = models.CharField(max_length=20, choices=Modalities.choices)
    """The diagnostic modality that was used to reach the diagnosis."""
    #:
    diagnose_date = RobustDateField(blank=True, null=True)
    #: diagnosed side
    side = models.CharField(max_length=10, choices=[("ipsi", "ipsi"),
                                                    ("contra", "contra")])

    LNLs = [
        "I", "Ia" , "Ib", "II", "IIa", "IIb", "III", "IV", "V", "Va", "Vb", "VII"
    ]
    """List of implemented lymph node levels. When the `models` module is
    imported, a simple for-loop creates additional fields for the `Diagnose`
    class for each of the elements in this list."""

    def __str__(self):
        """Report some info for admin view."""
        return (f"#{self.pk}: {self.get_modality_display()} diagnose "
                f"({self.side}) of patient #{self.patient.pk}")

    def save(self, *args, **kwargs):
        """
        Make sure LNLs and their sublevels (e.g. 'a' and 'b') are treated
        consistelntly. E.g. when sublevel ``Ia`` is reported to be involved,
        the involvement status of level ``I`` cannot be reported as healthy.

        Also, if all LNLs are reported as unknown (``None``), just delete it.
        """
        if all([getattr(self, lnl) is None for lnl in self.LNLs]):
            super().save(*args, **kwargs)
            return self.delete()

        safe_negate = lambda x: False if x is None else not x

        # LNL I (a and b)
        if self.Ia or self.Ib:
            self.I = True
        elif safe_negate(self.Ia) and safe_negate(self.Ib):
            self.I = False

        # LNL II (a and b)
        if self.IIa or self.IIb:
            self.II = True
        elif safe_negate(self.IIa) and safe_negate(self.IIb):
            self.II = False

        # LNL V (a and b)
        if self.Va or self.Vb:
            self.V = True
        elif safe_negate(self.Va) and safe_negate(self.Vb):
            self.V = False

        return super().save(*args, **kwargs)


# add lymph node level fields to model 'Diagnose'
for lnl in Diagnose.LNLs:
    Diagnose.add_to_class(lnl, models.BooleanField(blank=True, null=True))
