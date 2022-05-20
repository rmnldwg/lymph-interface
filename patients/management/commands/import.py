from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from patients.ioports import import_from_pandas


class Command(BaseCommand):
    """
    Populate the database with patients from a LyProX-style CSV table.
    """
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "filepath", type=str, help="Path to CSV table"
        )
        parser.add_argument(
            "usermail", type=str, help="Email of user uploading the table"
        )

    def handle(self, *args, **options):
        filepath = Path(options["filepath"]).resolve()
        table = pd.read_csv(filepath, header=[0,1,2])

        try:
            user = User.objects.get(email=options["usermail"])
        except User.DoesNotExist:
            user = User.objects.get(email="roman.ludwig@usz.ch")

        try:
            num_new, num_skipped = import_from_pandas(table, user)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {num_new} patients and skipped {num_skipped}."
                )
            )
        except Exception as exc:
            raise CommandError(f"Importing of file {filepath} failed.") from exc
