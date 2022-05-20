"""
Module for routing database queries to the correct database. In our case, all
queries go to the default database except the ones related to the patients.
We do this, so that we can safely reset the patient database and reimport the
entries, e.g. from [`lyDATA`], without losing the users and institutions.

[`lyDATA`]: https://github.com/rmnldwg/lydata
"""
import logging

from core import settings

logger = logging.getLogger(__name__)

class PatientsRouter:
    """
    Router to control operations on patient, tumor and diagnose models in the
    `patients` app.
    """

    def db_for_read(self, model, **hints):
        """
        Suggest database for read operations on models in the `patients` app.
        """
        if "patients_db" not in settings.DATABASES:
            return None
        if model._meta.app_label == "patients":
            return "patients_db"
        return None

    def db_for_write(self, model, **hints):
        """
        Suggest database for write operations on models in the `patients` app.
        """
        if "patients_db" not in settings.DATABASES:
            return None
        if model._meta.app_label == "patients":
            return "patients_db"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between with Patients, Tumors and Diagnoses.
        """
        if "patients_db" not in settings.DATABASES:
            return None
        if (
            obj1._meta.app_label == "patients" or
            obj2._meta.app_label == "patients"
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Allow migrations of models in the `patients` app.
        """
        if app_label == "patients":
            return db == "patients_db"
        return False
