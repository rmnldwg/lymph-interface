import logging

from django.contrib.auth.mixins import UserPassesTestMixin

logger = logging.getLogger(__name__)

from typing import Optional

from .models import Patient


class InstitutionCheckPatientMixin(UserPassesTestMixin):
    """Mixin that makes sure only users from the institution that created the
    patient can edit it.
    """
    def test_func(self) -> Optional[bool]:
        user = self.request.user
        patient = self.model.objects.get(**self.kwargs)
        msg = (f"User {user} is trying to edit/delete patient {patient}.")
        logger.info(msg)
        if user.is_superuser or user.institution == patient.institution:
            msg = ("Access granted")
            logger.info(msg)
            return True
        else:
            msg = ("Access denied")
            logger.info(msg)
            return False


class InstitutionCheckObjectMixin(UserPassesTestMixin):
    """Mixin that makes sure only users from the institution that created the
    patient can edit that patient's diagnose and tumor.
    """
    def test_func(self) -> Optional[bool]:
        user = self.request.user
        patient = Patient.objects.get(pk=self.kwargs["pk"])
        msg = (f"User {user} is trying to edit/delete a {self.model} on "
               f"patient {patient}.")
        logger.info(msg)
        if user.is_superuser or user.institution == patient.institution:
            msg = ("Access granted")
            logger.info(msg)
            return True
        else:
            msg = ("Access denied")
            logger.info(msg)
            return False
