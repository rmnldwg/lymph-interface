{% load mytags %}

Choose which of the available modalities to include in the visualization. Only patients
are considered that have at least one of the selected diagnoses available. One may
choose how to combine these - possibly conflicting - diagnoses:

- logical **OR**: A lymph node level (LNL) is reported as _metastatic_ or _involved_ as soon as one of the selected diagnoses reports a positive finding. Anything else is reported as _healthy_.
- logical **AND**: LNL's are reported as involved only when *all* diagnoses agree on positive findings. If that is not the case, meaning that none or not all agree on such a finding, it is reported (rather optimistically) as _healthy_.
- **maxLLH**: This computes the most likely involvement based on all available diagnostic modalities and their respective sensitivities & specificities for a patient.
- **rank**: Similar to the **maxLLh** method, this uses the sensitivities & specificities of the available diagnostic modalities, but instead of combining all diagnoses into one, it accepts the most trustworthy diagnose for a given patient.

The sensitivities & specificities used are listed below:

<table>
    <tr>
        <th>Modality</th>
        <th>Specificity</th>
        <th>Sensitivity</th>
    </tr>
    {% for modality in modalities %}
    <tr>
        <td>{{ modality.label }}</td>
        <td>{{ modality.spec | multiply:100 }}%</td>
        <td>{{ modality.sens | multiply:100 }}%</td>
    </tr>
    {% endfor %}
</table>
