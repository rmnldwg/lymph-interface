"""Command to add risk prediction models to database."""
import json
from pathlib import Path

from django.core.management import base
from django.db import IntegrityError

from lyprox.riskpredictor.models import InferenceResult


class Command(base.BaseCommand):
    """Command to add risk prediction models to database."""
    help = __doc__

    def add_arguments(self, parser):
        """Add arguments to command."""
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--from-file",
            type=Path,
            help="Path to JSON file with list of risk models.",
        )
        group.add_argument(
            "--from-stdin",
            action="store_true",
            help="Use command line arguments to create a single risk model.",
        )
        parser.add_argument(
            "--git-repo-owner", type=str, default="rmnldwg",
            help="Owner of git repository.",
        )
        parser.add_argument(
            "--git-repo-name", type=str, default="lynference",
            help="Name of git repository.",
        )
        parser.add_argument(
            "--revision", type=str,
            help="Revision of git repository.",
        )
        parser.add_argument(
            "--params-path", type=str, default="params.yaml",
            help="Path to YAML params in git repository.",
        )
        parser.add_argument(
            "--num-samples", type=int, default=100,
            help="Number of samples used.",
        )

    def handle(self, *args, **options):
        """Execute command."""
        if not options["from_stdin"]:
            with open(options["from_file"], encoding="utf-8") as json_file:
                riskmodel_configs = json.load(json_file)
        else:
            riskmodel_configs = [{
                "repo_name": options["repo_name"],
                "ref": options["ref"],
                # TODO: add remaining fields
            }]

        for config in riskmodel_configs:
            try:
                InferenceResult.objects.create(**config)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"InferenceResult '{config['revision']}' created."
                    )
                )
            except IntegrityError:
                self.stdout.write(
                    self.style.WARNING(
                        f"InferenceResult from repo_name='{config['repo_name']}' and "
                        f"ref='{config["ref"]}' already exists."
                    )
                )
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f"InferenceResult from repo_name='{config['repo_name']}' and "
                        f"ref='{config["ref"]}' could not be created doe to {exc}"
                    )
                )
