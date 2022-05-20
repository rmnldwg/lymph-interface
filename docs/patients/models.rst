.. module:: patients.models

======
Models
======

We represent each patient as an entry in the database that is defined in Django
as a model :class:`Patient`. For the necessary flexibility we built separate
models :class:`Tumor` and :class:`Diagnose` that can be added to a patient.
This way, a patient can have multiple tumors and many diagnoses.

In this document, we outline the fields and methods we added to Django's base
class :class:`django.db.models.base.Model` to adapt it to our purpose.


Patient
-------

.. autoclass:: patients.models.Patient
    :members:
    :show-inheritance:


Tumor
-----

.. autoclass:: patients.models.Tumor
    :members:
    :show-inheritance:


Diagnose
--------

.. autoclass:: patients.models.Diagnose
    :members:
    :show-inheritance:
