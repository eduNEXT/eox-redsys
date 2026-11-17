"""
eox-redsys Django application initialization.
"""
from django.apps import AppConfig


class EoxRedsysConfig(AppConfig):
    """
    Configuration for the eox-redsys Django application.

    Installed in the LMS through the ``lms.djangoapp`` entry point so its templates are found. The processor is
    registered separately, through the ``zeitlabs_payments.v1`` entry point, and its views are mounted by zeitlabs.
    """

    name = 'eox_redsys'
    verbose_name = 'eox-redsys'
