


def test_patient(patient_factory):
    patient = patient_factory.build()
    print(patient.hash_value)
    print(patient.age)
    print(patient.get_t_stage_display())
    print(patient.institution.name)
