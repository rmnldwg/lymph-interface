import time
import logging
from typing import Dict, List, Optional

import numpy as np
from django.db.models import Q, QuerySet

from accounts.models import Institution
from patients.models import Diagnose, Patient, Tumor

logger = logging.getLogger(__name__)


def tf2arr(value):
    """Map `True`, `False` & `None` to one-hot-arrays of length 3. This
    particular mapping comes from the fact that in the form `True`, `None`,
    `False` are represented by integers 1, 0, -1. So, the one-hot encoding
    uses an array of length 3 that is one only at these respective indices,
    where -1 is the last item."""
    if value is None:
        return np.array([1, 0, 0], dtype=int)
    else:
        if value:
            return np.array([0, 1, 0], dtype=int)
        else:
            return np.array([0, 0, 1], dtype=int)


def subsite2arr(subsite):
    """Map different subsites to an one-hot-array of subsite groups. E.g., a
    one in the first place means "base of tongue", at the second place is
    "tonsil" and so on.
    """
    res = np.zeros(shape=len(Tumor.SUBSITE_DICT), dtype=int)

    for i,subsite_list in enumerate(Tumor.SUBSITE_DICT.values()):
        if subsite in subsite_list:
            res[i] = 1

    if np.sum(res) > 1:
        logger.warn("A tumor has been associated with more than one subsite.")

    return res


def patient_specific(
    patient_queryset: QuerySet = Patient.objects.all(),
    nicotine_abuse: Optional[bool] = None,
    hpv_status: Optional[bool] = None,
    neck_dissection: Optional[bool] = None,
    institution__in: Optional[Institution] = None,
    **rest
) -> QuerySet:
    """Filter `QuerySet` of `Patient`s based on patient-specific properties.
    """
    kwargs = locals()
    start_time = time.perf_counter()
    kwargs.pop('patient_queryset')
    kwargs.pop('rest')

    # the form fields are named such that they can be inserted into the
    # QuerySet filtering function directly
    for key, value in kwargs.items():
        if value is not None:
            patient_queryset = patient_queryset.filter(**{key: value})

    end_time = time.perf_counter()
    logger.debug(f"Patient-specific querying done in {end_time - start_time:.3f} s.")
    return patient_queryset


def tumor_specific(
    patient_queryset: QuerySet = Patient.objects.all(),
    # restrict to Oropharynx
    subsite__in: List[str] = Tumor.SUBSITE_LIST,
    t_stage__in: List[int] = [1,2,3,4],
    central: Optional[bool] = None,
    extension: Optional[bool] = None,
    **rest
) -> QuerySet:
    """Filter `QuerySet` of `Patient`s based on tumor-specific properties.
    """
    kwargs = locals()              # extract keyword arguments and...
    start_time = time.perf_counter()
    kwargs.pop('patient_queryset') # ...remove the patient queryset and...
    kwargs.pop('rest')             # ...any other kwargs from this dictionary.
    for key, value in kwargs.items():   # iterate over provided kwargs and ...
        if value is not None:             # ...if it's of interest, then filter
            patient_queryset = patient_queryset.filter(**{f'tumor__{key}': value})

    end_time = time.perf_counter()
    logger.debug(f"Tumor-specific querying done in {end_time - start_time:.3f} s.")
    return patient_queryset


def diagnose_specific(
    patient_queryset: QuerySet = Patient.objects.all(),
    **kwargs
):
    """"""
    logger.debug(kwargs["modalities"])
    start_time = time.perf_counter()
    
    # get diagnoses for all patients and the selected modalities
    d = Diagnose.objects.all().filter(patient__in=patient_queryset,
                                      modality__in=kwargs['modalities'])
    q_ipsi = Q(side="ipsi")

    d_ipsi = d.filter(q_ipsi)
    d_contra = d.exclude(q_ipsi)
    diagnose_querysets = {
        'ipsi'  : d_ipsi.select_related('patient').values(),
        'contra': d_contra.select_related('patient').values()
    }

    # remove patients that don't have any of the diagnoses left
    patient_queryset = patient_queryset.filter(
        Q(diagnose__in=d_ipsi) | Q(diagnose__in=d_contra)
    ).distinct()

    selected_diagnose = {
        'ipsi'  : np.array([None] * len(Diagnose.LNLs)),
        'contra': np.array([None] * len(Diagnose.LNLs))
    }
    diagnose_tables = {       # this will hold a table with rows for each 
        'ipsi'  : {},         # modality and columns for each LNL for each 
        'contra': {}          # patient, holding the involvement information.
    }
    combined_involvement = {  # the above tables will be reduced along the 
        'ipsi'  : {},         # columns to produce the 'consensus', which will 
        'contra': {}          # be stored in these dictionaries per patient.
    }
    for side in ['ipsi', 'contra']:
        for i,lnl in enumerate(Diagnose.LNLs):
            if (selected_inv := kwargs[f'{side}_{lnl}']) is not None:
                selected_diagnose[side][i] = selected_inv

        for diagnose in diagnose_querysets[side]:
            patient_id = diagnose['patient_id']
            # double square brackets below to make sure the `diag_array` is 
            # two-dimensional. Without it, `np.all(, axis=0)` wouldn't work
            diag_array = np.array([[diagnose[f'{lnl}'] for lnl in Diagnose.LNLs]])

            if patient_id in diagnose_tables[side]:
                diagnose_tables[side][patient_id] = np.vstack([
                    diagnose_tables[side][patient_id],
                    diag_array
                ])
            else:
                diagnose_tables[side][patient_id] = diag_array

        for patient_id, diag_table in diagnose_tables[side].items():
            if kwargs['modality_combine'] == 'OR':
                combine = any
            elif kwargs['modality_combine'] == 'AND':
                # same as `all`, but handles `None` correctly by ignoring it
                combine = lambda col: not(any(
                    [not(e) if e is not None else None for e in col]
                ))
            else:
                msg = "Can only combine modalities using OR or AND (logical)"
                logger.error(msg)
                raise ValueError(msg)

            try:
                combined_involvement[side][patient_id] = np.array(
                    [combine(col) for col in diag_table.T],
                    dtype=object
                )
            except TypeError:  # difference: square bracket around `col`
                combined_involvement[side][patient_id] = np.array(
                    [combine([col]) for col in diag_table.T],
                    dtype=object
                )
            # when all observations yield 'unknown' for a LNL, report 'unknown'
            all_none_idx = np.all(diag_table == None, axis=0)
            combined_involvement[side][patient_id][all_none_idx] = None

            mask = selected_diagnose[side] != None
            match = np.all(np.equal(combined_involvement[side][patient_id],
                                    selected_diagnose[side],
                                    where=mask,
                                    out=np.ones_like(mask, dtype=bool)))
            if not match:   # if it does not match, remove patient from queryset
                patient_queryset = patient_queryset.exclude(id=patient_id)

    end_time = time.perf_counter()
    logger.info(f"Diagnose-specific querying done in {end_time - start_time:.3f} s")
    return patient_queryset, combined_involvement


def n_zero_specific(
    patient_queryset: QuerySet,
    combined_involvement: Dict[str, Dict[str, np.ndarray]],
    n_status: Optional[bool] = None
):
    """Filter for N+ or N0. `n_status` is `True` when we only want to see N+
    patients and `False` when we only want to see N0 patients.
    """
    if n_status is None:
        return patient_queryset, combined_involvement

    patients = patient_queryset.values("id")
    for pat in patients:
        pat_id = pat["id"]
        try:
            has_ipsi_inv = any(combined_involvement["ipsi"][pat_id])
        except KeyError:
            has_ipsi_inv = False

        try:
            has_contra_inv = any(combined_involvement["contra"][pat_id])
        except KeyError:
            has_contra_inv = False

        if n_status and not (has_ipsi_inv or has_contra_inv):
            patient_queryset = patient_queryset.exclude(id=pat_id)
        elif not n_status and (has_ipsi_inv or has_contra_inv):
            patient_queryset = patient_queryset.exclude(id=pat_id)

    return patient_queryset, combined_involvement


def count_patients(
    patient_queryset: QuerySet,
    combined_involvement: Dict[str, Dict[str, np.ndarray]]
):
    """Count how often patients have various characteristics like HPV status,
    certain lymph node level involvement, and so on.
    """
    start_time = time.perf_counter()
    # prefetch patients and important fields for performance
    patients = patient_queryset.prefetch_related('tumor_set')

    # get a QuerySet of all institutions
    institutions = Institution.objects.all()

    counts = {   # initialize counts of patient- & tumor-related fields
        'total': len(patients),

        'institutions': np.array([
            len(patients.filter(institution=inst)) for inst in institutions
        ], dtype=int),

        'sex': np.zeros(shape=(3,), dtype=int),
        'nicotine_abuse': np.zeros(shape=(3,), dtype=int),
        'hpv_status': np.zeros(shape=(3,), dtype=int),
        'neck_dissection': np.zeros(shape=(3,), dtype=int),
        'n_status': np.zeros(shape=(3,), dtype=int),

        'subsites': np.zeros(shape=len(Tumor.SUBSITE_DICT), dtype=int),
        't_stages': np.zeros(shape=(len(Patient.T_stages),), dtype=int),
        'central': np.zeros(shape=(3,), dtype=int),
        'extension': np.zeros(shape=(3,), dtype=int),
    }
    for side in ['ipsi', 'contra']:
        for lnl in Diagnose.LNLs:
            counts[f'{side}_{lnl}'] = np.zeros(shape=(3,), dtype=int)

    # loop through patients to populate the counts dictionary
    for patient in patients:
        # PATIENT specific counts
        counts['nicotine_abuse'] += tf2arr(patient.nicotine_abuse)
        counts['hpv_status'] += tf2arr(patient.hpv_status)
        counts['neck_dissection'] += tf2arr(patient.neck_dissection)

        # TUMOR specific counts
        tumor = patient.tumor_set.first()
        counts['subsites'] += subsite2arr(tumor.subsite)
        counts['t_stages'][tumor.t_stage-1] += 1
        counts['central'] += tf2arr(tumor.central)
        counts['extension'] += tf2arr(tumor.extension)

        # N0/N+ counts
        has_contra = np.any(combined_involvement["contra"][patient.id])
        has_ipsi = np.any(combined_involvement["ipsi"][patient.id])
        if not has_ipsi and not has_contra:
            counts['n_status'] += np.array([0,0,1])
        else:
            counts['n_status'] += np.array([0,1,0])

        # DIAGNOSE specific (involvement) counts
        for side in ['ipsi', 'contra']:
            for i,lnl in enumerate(Diagnose.LNLs):
                try:
                    tmp = combined_involvement[side][patient.id][i]
                except KeyError:
                    # Not all patients have symmetric diagnoses
                    pass
                counts[f'{side}_{lnl}'] += tf2arr(tmp)

    end_time = time.perf_counter()
    logger.info(f"Generating stats done after {end_time - start_time:.3f} s")
    return patient_queryset, counts