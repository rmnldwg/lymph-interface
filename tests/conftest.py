from factories import (
    DiagnoseFactory,
    InstitutionFactory,
    PatientFactory,
    TumorFactory,
    UserFactory,
)
from pytest_factoryboy import register

register(UserFactory)
register(InstitutionFactory)
register(PatientFactory)
register(TumorFactory)
register(DiagnoseFactory)
