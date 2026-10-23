from django.core.management.base import BaseCommand, CommandError

from cba_production.learning_credits.processing import process_pending_requests


class Command(BaseCommand):
    help = "Process a bounded batch of due CBA credit requests."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        try:
            counts = process_pending_requests(limit=options["limit"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            " ".join(f"{name}={value}" for name, value in counts.items())
        )
