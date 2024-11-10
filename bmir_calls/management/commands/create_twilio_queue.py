from django.conf import settings
from django.core.management.base import BaseCommand

from ...twilio import create_or_find_queue


class Command(BaseCommand):
    help = "Create queue on Twilio"

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Delete queue instead of creating it.")
        parser.add_argument(
            "-n",
            "--name",
            help=f"Queue name (default from settings.py: {settings.TWILIO_QUEUE_NAME})",
            default=settings.TWILIO_QUEUE_NAME,
        )

    def handle(self, *args, **options):
        queue = create_or_find_queue(options["name"], create=not options["delete"])
        if options["delete"]:
            if queue is None:
                self.stdout.write(self.style.WARNING(f"Queue named {options['name']} not found."))
            else:
                queue.delete()
                self.stdout.write(self.style.SUCCESS(f"Queue named {options['name']} (sid: {queue.sid}) deleted."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Queue named {options['name']} (sid: {queue.sid}, size: {queue.max_size}) created.")
            )
