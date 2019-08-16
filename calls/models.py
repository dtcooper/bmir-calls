from collections import namedtuple
import datetime
import random

from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.expression import (
    cast,
    nullsfirst,
)
import pytz

from flask import current_app as app
from flask_sqlalchemy import SQLAlchemy

from calls.utils import sanitize_phone_number


db = SQLAlchemy()


class VolunteerBase:
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    phone_number = db.Column(db.String(20), nullable=False)
    opt_in_hours = db.Column(postgresql.ARRAY(db.SmallInteger, dimensions=1), nullable=False, default=list(range(24)))
    country_code = db.Column(db.String(2), nullable=False, default='??')

    def serialize(self):
        data = {col.name: getattr(self, col.name) for col in self.__table__.columns}

        # Make dates nice, and converted to server tz
        for column in self.__table__.columns:
            if isinstance(column.type, db.DateTime):
                value = data[column.name]
                if value:
                    data[column.name] = str(value.astimezone(app.config['SERVER_TZ']))

        return data

    @db.validates('country_code', 'phone_number', 'timezone')
    def validate_code(self, key, value):
        max_len = getattr(self.__class__, key).prop.columns[0].type.length
        if value and len(value) > max_len:
            return value[:max_len]
        return value

    def __repr__(self):
        return '<{} {}>'.format(
            self.__class__.__name__, self.phone_number)


class Submission(VolunteerBase, db.Model):
    __tablename__ = 'submissions'
    timezone = db.Column(db.String(255), nullable=False, default='')
    valid_phone = db.Column(db.Boolean, nullable=False, default=True)

    def get_volunteer_kwargs(self):
        kwargs = {
            name: getattr(self, name)
            for name, column in VolunteerBase.__dict__.items()
            if isinstance(column, db.Column) and name != 'created'
        }
        kwargs['submission_id'] = kwargs.pop('id')

        return kwargs

    @classmethod
    def create_from_json(cls, json_data):
        kwargs = {
            # Strip user input
            key: val.strip() if isinstance(val, str) else val
            for key, val in json_data.items()
        }

        user_tz = app.config['SERVER_TZ']
        try:
            user_tz_str = kwargs['timezone']
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

            for i in range(app.config['FORM_HOUR_CHUNK_SIZE']):
                opt_in_hours.append((hour + i) % 24)

        kwargs.update({
            'opt_in_hours': sorted(opt_in_hours),
            'valid_phone': False,
        })

        phone_number, country_code = sanitize_phone_number(
            kwargs['phone_number'], with_country_code=True)
        if phone_number:
            kwargs.update({
                'phone_number': phone_number,
                'valid_phone': True,
                'country_code': country_code,
            })

        submission = cls(**kwargs)
        db.session.add(submission)
        db.session.commit()

        return submission

    def create_volunteer(self):
        if all([
            # Make sure we have a valid phone, with no existing volunteer
            self.opt_in_hours, self.valid_phone,
            not bool(Volunteer.query.filter_by(phone_number=self.phone_number).first()),
        ]):
            volunteer = Volunteer(**self.get_volunteer_kwargs())
            db.session.add(volunteer)
            db.session.commit()
            return volunteer
        else:
            return False


class Volunteer(VolunteerBase, db.Model):
    RANDOM_POOL_SIZE = 5

    __tablename__ = 'volunteers'
    submission_id = db.Column(db.Integer, nullable=False)
    updated = db.Column(db.DateTime(timezone=True), server_default=db.func.now(),
                        onupdate=db.func.now())
    last_called = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        # XXX https://stackoverflow.com/a/37403848
        db.Index('volunteers_phone_number_key', 'phone_number', unique=True),
        db.Index('volunteers_last_called_key', last_called,
                 postgresql_ops={'last_called': 'ASC NULLS FIRST'})
    )

    @classmethod
    def get_random_opted_in(cls, update_last_called=True, current_hour=None):
        if current_hour is None:
            current_hour = datetime.datetime.now(app.config['SERVER_TZ']).hour

        current_hour_smallint_array = cast([current_hour], db.ARRAY(db.SmallInteger))

        # Take the N least recently called volunteers, and pick one at random
        volunteers = cls.query.filter(
            # Finds a currently opted in volunteer, and performs on the gin index :)
            cls.opt_in_hours.contains(current_hour_smallint_array),
        ).order_by(nullsfirst(cls.last_called)).limit(
            cls.RANDOM_POOL_SIZE).all()

        if not volunteers:
            return None

        volunteer = random.choice(volunteers)

        if update_last_called:
            volunteer.last_called = datetime.datetime.now(app.config['SERVER_TZ'])
            db.session.add(volunteer)
            db.session.commit()

        return volunteer


class UserCodeConfig(db.Model):
    UserCode = namedtuple('UserCode', ('number', 'name', 'default', 'description'))
    CODES = (
        UserCode('0', 'random_weirdness_to_broadcast', True,
                 'Outside phone randomly calling the broadcast desk'),
        UserCode('1', 'broadcast_incoming', True, 'Broadcast desk phone ringer'),
        UserCode('2', 'random_broadcast_misses_to_weirdness', False,
                 'BMIR callers randomly calling the outside phone'),
        UserCode('3', 'weirdness_multiring', False, 'Ringing multiple callers'),
    )
    CODES_BY_NUMBER = {code.number: code for code in CODES}
    CODES_BY_NAME = {code.name: code for code in CODES}

    __tablename__ = 'user_code_config'

    name = db.Column(db.String(40), primary_key=True)
    value = db.Column(db.Boolean(), nullable=False)

    @classmethod
    def get_code_by_number(cls, number):
        return cls.CODES_BY_NUMBER.get(number)

    @classmethod
    def get(cls, name):
        code = cls.CODES_BY_NAME.get(name)
        if not code:
            return None
        config = cls.query.filter_by(name=code.name).first()
        return config.value if config else code.default

    @classmethod
    def set(cls, name, value):
        code = cls.CODES_BY_NAME.get(name)
        if code:
            config = cls.query.filter_by(name=code.name).first()

            if config:
                config.value = value
            else:
                config = cls(name=code.name, value=value)
            db.session.add(config)
            db.session.commit()

    def __repr__(self):
        return '<UserCodeConfig {}={!r}>'.format(self.name, self.value)
