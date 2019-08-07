import datetime
import pytz

from twilio.base.exceptions import TwilioRestException

from flask import current_app as app
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


dbnow = db.func.current_timestamp()


class VolunteerBase:
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime(timezone=True), default=db.func.current_timestamp())
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    opt_in_hours = db.Column(db.ARRAY(db.SmallInteger), nullable=False, default=[])
    comments = db.Column(db.Text, nullable=False, default='')

    @db.validates('name', 'email', 'phone_number')
    def validate_code(self, key, value):
        max_len = getattr(self.__class__, key).prop.columns[0].type.length
        if value and len(value) > max_len:
            return value[:max_len]
        return value


class Submission(VolunteerBase, db.Model):
    __tablename__ = 'submissions'
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    valid_phone = db.Column(db.Boolean, nullable=False, default=True)

    @classmethod
    def from_json(cls, json_data):
        kwargs = {
            # Strip user input
            key: val.strip() if isinstance(val, str) else val
            for key, val in json_data.items()
        }

        user_tz = app.config['SERVER_TZ']
        try:
            user_tz_str = kwargs.pop('timezone')
            if user_tz_str:
                # Last word in string, trim out brackets
                user_tz = pytz.timezone(user_tz_str.split()[-1][1:-1])
        except (pytz.UnknownTimeZoneError, IndexError):
            pass

        opt_in_hours = []
        for opt_in_time_raw in (kwargs['opt_in_hours'] or ()):
            hour = opt_in_time_raw.strip().lower().split(' - ')[0]
            if hour == 'midnight':
                hour = 0
            elif hour == 'noon':
                hour = 12
            else:
                suffix = hour[-2:]
                hour = int(hour[:-2], 10)
                if suffix == 'pm':
                    hour += 12

            # Localize hour on conversion date to user's timezone, then convert
            # to server's timezone and take the hour
            hour = user_tz.localize(datetime.datetime.combine(
                app.config['DATE_FOR_TZ_CONVERSION'],
                datetime.time(hour=hour),
            )).astimezone(app.config['SERVER_TZ']).hour

            # Form is in two hour chunks
            opt_in_hours.extend([hour, (hour + 1) % 24])

        kwargs['opt_in_hours'] = sorted(opt_in_hours)

        try:
            kwargs['phone_number'] = app.twilio.lookups.phone_numbers(
                kwargs['phone_number']).fetch(country_code='US').phone_number
            kwargs['valid_phone'] = True
        except TwilioRestException:
            kwargs['valid_phone'] = False

        return cls(**kwargs)


class Volunteer(VolunteerBase, db.Model):
    __tablename__ = 'volunteers'
    submission_id = db.Column(db.Integer)
    updated = db.Column(db.DateTime(timezone=True), default=db.func.current_timestamp(),
                        onupdate=db.func.current_timestamp())
    last_called = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        # XXX https://stackoverflow.com/a/37403848
        db.Index('volunteers_eligibility_key', 'opt_in_hours', postgresql_using='gin'),
        db.Index('volunteers_phone_number_key', 'phone_number', unique=True),
    )
