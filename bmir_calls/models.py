import datetime

from django.db import models

from phonenumber_field.modelfields import PhoneNumberField


LOCATION_UNKNOWN = "Unknown"


class Voicemail(models.Model):
    created_at = models.DateTimeField("created at", auto_now_add=True, db_index=True)
    phone_number = PhoneNumberField("phone number", blank=True)
    location = models.CharField(max_length=256, default=LOCATION_UNKNOWN)
    duration = models.DurationField("duration", default=datetime.timedelta(0))
    file = models.FileField("audio file", upload_to="voicemails/")

    def __str__(self):
        return f"Voicemail from {self.phone_number or 'unknown'} ({self.duration})"

    class Meta:
        ordering = ("-created_at", "id")
        get_latest_by = "created_at"
