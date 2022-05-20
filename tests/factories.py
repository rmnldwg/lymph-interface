import factory
import numpy as np
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker()
# Faker.seed(42)

from accounts.models import Institution, User
from patients.models import Diagnose, Patient, Tumor


class InstitutionFactory(DjangoModelFactory):
    class Meta:
        model = Institution

    name = f"{fake.name()} Hospital"
    city = fake.city()
    street = f"{fake.street_name()} {np.random.randint(low=1, high=255)}"
    country = fake.country()
    phone = fake.phone_number()
    shortname = "".join([w[0].upper() for w in f"{name} {city}".split(" ")])


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    institution = factory.SubFactory(InstitutionFactory)

    first_name = fake.first_name()
    last_name = fake.last_name()
    email = f"{first_name.lower()}.{last_name.lower()}@mail.com"
    is_staff = False
    is_superuser = False

    password = fake.password()


class PatientFactory(DjangoModelFactory):
    class Meta:
        model = Patient

    class Params:
        first_name = fake.first_name()
        last_name = fake.last_name()
        birthday = fake.date_of_birth(minimum_age=14)

    hash_value = factory.LazyAttribute(
        lambda o: hash((o.first_name, o.last_name, o.birthday))
    )
    gender = fake.random_element(elements=["male", "female"])
    diagnose_date = factory.LazyAttribute(
        lambda o: fake.date_between_dates(date_start=o.birthday)
    )
    age = factory.LazyAttribute(
        lambda o: o.diagnose_date.year - o.birthday.year
    )

    alcohol_abuse = fake.random_element(elements=[True, False, None])
    nicotine_abuse = fake.random_element(elements=[True, False, None])
    hpv_status = fake.random_element(elements=[True, False, None])
    neck_dissection = fake.random_element(elements=[True, False, None])

    t_stage = fake.random_element(elements=Patient.T_stages.values)
    n_stage = fake.random_element(elements=Patient.N_stages.values)
    m_stage = fake.random_element(elements=Patient.M_stages.values)

    institution = factory.SubFactory(InstitutionFactory)


SUBSITE_LIST = [
    "C03.0", "C03.1", "C03.9", "C04.0", "C04.1", "C04.8", "C04.9", "C05.0",
    "C05.1", "C05.2", "C05.8", "C05.9", "C06.0", "C06.1", "C06.2", "C06.8",
    "C06.9", "C01.9", "C09.0", "C09.1", "C09.8", "C09.9", "C10.0", "C10.1",
    "C10.2", "C10.3", "C10.4", "C10.8", "C10.9", "C12.9", "C13.0", "C13.1",
    "C13.2", "C13.8", "C13.9", "C32.0", "C32.1", "C32.2", "C32.3", "C32.8",
    "C32.9"
]

class TumorFactory(DjangoModelFactory):
    class Meta:
        model = Tumor

    patient = factory.SubFactory(PatientFactory)

    location = fake.random_element(elements=Tumor.Locations.values)
    subsite = fake.random_element(elements=SUBSITE_LIST)
    side = fake.random_element(elements=["right", "left", "central"])

    extension = fake.random_element(elements=[True, False, None])
    volume = fake.pyfloat(min_value=0., max_value=100.)

    t_stage = fake.random_element(elements=Patient.T_stages.values)
    stage_prefix = fake.random_element(elements=["c", "p"])


class DiagnoseFactory(DjangoModelFactory):
    class Meta:
        model = Diagnose

    patient = factory.SubFactory(PatientFactory)

    modality = fake.random_element(elements=Diagnose.Modalities.values)
    diagnose_date = fake.date_between(start_date='-12y')

    side = fake.random_element(elements=["left", "right"])

    Ia  = fake.random_element(elements=[True, False, None])
    Ib  = fake.random_element(elements=[True, False, None])
    I   = factory.LazyAttribute(lambda o: any([o.Ia, o.Ib]))
    IIa = fake.random_element(elements=[True, False, None])
    IIb = fake.random_element(elements=[True, False, None])
    II  = factory.LazyAttribute(lambda o: any([o.IIa, o.IIb]))
    III = fake.random_element(elements=[True, False, None])
    IV  = fake.random_element(elements=[True, False, None])
    V   = fake.random_element(elements=[True, False, None])
    VII = fake.random_element(elements=[True, False, None])
