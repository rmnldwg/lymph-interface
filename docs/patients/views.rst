.. module:: patients.views

=====
Views
=====

The view classes and methods are responsible for filling HTML templates with
information and rendering out a response to a user's request. In our project,
we were able to use class-based views quite extensively, relying on pre-built
functionalities to create, edit, inspect and delete objects.

Patient
-------

.. autoclass:: patients.views.CreatePatientView
    :members:
    :show-inheritance:

.. autoclass:: patients.views.UpdatePatientView
    :members:
    :show-inheritance:

.. autoclass:: patients.views.DeletePatientView
    :members:
    :show-inheritance:

.. autoclass:: patients.views.PatientDetailView
    :members:
    :show-inheritance:

.. autoclass:: patients.views.PatientListView
    :members:
    :show-inheritance:


Tumor
-----

Views to display, create, edit and delete the tumor(s) of a patient are always
shown as part of the :class:`PatientDetailView`.

.. autoclass:: patients.views.CreateTumorView
    :members:
    :show-inheritance:

.. autoclass:: patients.views.UpdateTumorView
    :members:
    :show-inheritance:

.. autoclass:: patients.views.DeleteTumorView
    :members:
    :show-inheritance:


Diagnose
--------

Like the tumor, a diagnose isn't displayed alone (or created/edited in
isolation), but always in the context and view of the patient it belongs to.

.. autoclass:: patients.views.CreateDiagnoseView
    :members:
    :show-inheritance:

.. autoclass:: patients.views.UpdateDiagnoseView
    :members:
    :show-inheritance:

.. autoclass:: patients.views.DeleteDiagnoseView
    :members:
    :show-inheritance:


Batch up- & down-loading
------------------------

.. autofunction:: patients.views.upload_patients

.. autofunction:: patients.views.generate_and_download_csv
