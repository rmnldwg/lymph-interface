"""
Module for functions to predict the risk of lymphatic progression.

The code in this module is utilized by the `views.RiskPredictionView` of the
`riskpredictor` app to compute the risk of lymphatic progression for a given diagnosis.
"""

import logging
from typing import Annotated, Any, Literal, TypeVar

import numpy as np
from lydata.utils import ModalityConfig
from lymph.models import HPVUnilateral, Unilateral
from lymph.types import Model
from lyscripts.configs import DiagnosisConfig, add_modalities
from pydantic import AfterValidator, BaseModel, create_model

from lyprox.dataexplorer.query import make_ensure_keys_validator
from lyprox.riskpredictor.models import CheckpointModel

logger = logging.getLogger(__name__)


NullableBoolPercents = Annotated[
    dict[Literal[True, False, None], float],
    AfterValidator(make_ensure_keys_validator([True, False, None])),
]
"""Keys may be ``True``, ``False``, or ``None``, while values are the counts of each."""


def compute_posteriors(
    model: Model,
    priors: np.ndarray,
    diagnosis: DiagnosisConfig,
    specificity: float = 0.9,
    sensitivity: float = 0.9,
) -> np.ndarray:
    """Compute the posterior state dists for the given model, priors, and diagnosis."""
    modality_config = ModalityConfig(spec=specificity, sens=sensitivity)
    model = add_modalities(model=model, modalities={"D": modality_config})
    posteriors = []

    if isinstance(model, Unilateral | HPVUnilateral):
        diagnosis = diagnosis.ipsi
    else:
        diagnosis = diagnosis.model_dump()

    for prior in priors:
        posterior = model.posterior_state_dist(
            given_state_dist=prior,
            given_diagnosis=diagnosis,
        )
        posteriors.append(posterior)

    return np.stack(posteriors)


def assemble_diagnosis(
    form_data: dict[str, Any],
    lnls: list[str],
    modality: str = "D",
) -> DiagnosisConfig:
    """Create a `DiagnosisConfig` object from the cleaned form data."""
    diagnosis_dict = {}

    for side in ["ipsi", "contra"]:
        diagnosis_dict[side] = {modality: {}}
        for lnl in lnls:
            if f"{side}_{lnl}" not in form_data:
                continue
            diagnosis_dict[side][modality][lnl] = form_data[f"{side}_{lnl}"]

    return DiagnosisConfig(**diagnosis_dict)


def collect_risk_stats(
    risk_values: np.ndarray,
) -> dict[Literal[True, None, False], float]:
    """
    For an array of `risk_values`, collect the mean and std for each risk type.

    The format is chosen like the `lyprox.dataexplorer.query.Statistics` object that
    collects how many patients had `True`, `None`, or `False` involvement for a given
    LNL. In this case, under the key `True`, we store the marginalized risk of
    involvement in the respective LNL, under `None` two times the standard deviation,
    and under `False` the remaining number to sum to 100%.
    """
    risk_values = 100 * np.array(risk_values)
    mean = np.mean(risk_values, axis=0)
    std = np.std(risk_values, axis=0)
    return {
        True: mean,
        None: 2 * std,
        False: 100 - mean - 2 * std,
    }


BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


def compute_risks(
    checkpoint: CheckpointModel,
    form_data: dict[str, Any],
    lnls: list[str],
) -> BaseModelT:
    """
    Compute the risks for the given checkpoint and form data.

    Returns an instance of a dynamically created pydantic `BaseModel` class that has
    fields like `ipsi_II` or `contra_III`. In these fields, it stores the risk in
    dictionaries like:

    .. code-block:: python

        {
            True: 26.3,   # Risk of involvement in the respective LNL
            None: 5.2,    # Two times the standard deviation of the risk
            False: 68.5,  # Remaining number to sum to 100
        }

    This format is compatible with the `lyprox.dataexplorer.query.Statistics` object
    and thus also with the HTML templates used in the `dataexplorer` app.
    """
    model = checkpoint.construct_model()
    priors = checkpoint.compute_priors(t_stage=form_data["t_stage"])
    diagnosis = assemble_diagnosis(form_data=form_data, lnls=lnls)

    posteriors = compute_posteriors(
        model=model,
        priors=priors,
        diagnosis=diagnosis,
        specificity=form_data["specificity"],
        sensitivity=form_data["sensitivity"],
    )

    fields, kwargs = {}, {}
    for side in ["ipsi", "contra"]:
        for lnl in lnls:
            key = f"{side}_{lnl}"
            if key not in form_data:
                continue

            if isinstance(model, Unilateral | HPVUnilateral):
                involvement = {lnl: True}
            else:
                involvement = {side: {lnl: True}}

            kwargs[key] = collect_risk_stats(
                [
                    model.marginalize(involvement=involvement, given_state_dist=post)
                    for post in posteriors
                ]
            )
            fields[key] = (NullableBoolPercents, ...)

    return create_model("Risks", __base__=BaseModel, **fields)(**kwargs)
