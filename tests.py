import re
from unittest.mock import patch
import unittest

from sqlalchemy.engine.url import make_url
import pytz

from calls import app
from calls.models import (
    db,
    Submission,
    Volunteer,
)
from calls.utils import protected_url_for


class CallsTests(unittest.TestCase):
    def setUp(self):
        testing_db_uri = make_url(app.config['SQLALCHEMY_DATABASE_URI'])
        testing_db_uri.database = app.config['SQLALCHEMY_DATABASE_NAME_TESTING']

        self.twilio_patch = patch('calls.app.twilio')
        self.twilio_mock = self.twilio_patch.start()

        app.config.update({
            'TESTING': True,
            'DEBUG': False,
            'SERVER_NAME': 'example.com',
            'SQLALCHEMY_DATABASE_URI': str(testing_db_uri),
            'API_PASSWORD': 'test-password',
            'SERVER_TZ': pytz.timezone('US/Pacific'),
        })

        self.context = app.app_context()
        self.context.push()

        db.drop_all()
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        self.context.pop()
        self.twilio_patch.stop()

    def get_submit_json(self, bad_phone_number=False, **kwargs):
        json_data = {
            'email': 'test-user@example.com',
            'enabled': True,
            'name': 'Test User',
            'phone_number': '416-967-1111',
            'opt_in_hours': [
                'midnight - 2am', '2am - 4am', '4am - 6am', '6am - 8am',
                '8am - 10am', '10am - noon', 'noon - 2pm', '2pm - 4pm',
                '4pm - 6pm', '6pm - 8pm', '8pm - 10pm', '10pm - midnight'
            ],
            'timezone': '[GMT-07:00] Pacific Time // Black Rock City Time (US/Pacific)',
            'comments': 'This is a test comment',
        }
        json_data.update(kwargs)

        if bad_phone_number:
            mock_phone = False
        else:
            mock_phone = '+1{}'.format(re.sub(r'[^0-9]', '', json_data['phone_number']))
        self.twilio_mock.lookups.phone_numbers().fetch().phone_number = mock_phone

        return json_data

    @staticmethod
    def create_submission(**kwargs):
        defaults = {
            'email': 'test-user@example.com',
            'enabled': True,
            'name': 'Test User',
            'timezone': '[GMT-07:00] Pacific Time // Black Rock City Time (US/Pacific)',
            'comments': 'This is a test comment',
            'phone_number': '+14169671111',
            'opt_in_hours': list(range(24)),
            'valid_phone': True,
        }
        defaults.update(kwargs)
        submission = Submission(**defaults)
        db.session.add(submission)
        db.session.commit()
        return submission

    def test_form_submit(self):
        self.assertEqual(Submission.query.count(), 0)
        self.assertEqual(Volunteer.query.count(), 0)

        response = self.client.post(
            protected_url_for('volunteers.submit'), json=self.get_submit_json())
        self.assertEqual(response.status_code, 200)

        self.assertEqual(Submission.query.count(), 1)
        self.assertEqual(Volunteer.query.count(), 0)

        submission = Submission.query.first()
        self.assertEqual(submission.name, 'Test User')
        self.assertEqual(submission.email, 'test-user@example.com')
        self.assertEqual(submission.phone_number, '+14169671111')
        self.assertEqual(submission.opt_in_hours, list(range(24)))
        self.assertEqual(submission.comments, 'This is a test comment')
        self.assertTrue(submission.enabled)
        self.assertEqual(
            submission.timezone,
            '[GMT-07:00] Pacific Time // Black Rock City Time (US/Pacific)',
        )
        self.assertTrue(submission.valid_phone)

        self.twilio_mock.calls.create.assert_called_once_with(
            from_=app.config['WEIRDNESS_NUMBER'],
            to='+14169671111',
            url=protected_url_for('volunteers.verify', id=submission.id),
        )

    @unittest.skip("Implement don't call on no time slots")
    def test_form_submit_empty_vals(self):
        self.assertEqual(Submission.query.count(), 0)
        self.assertEqual(Volunteer.query.count(), 0)

        data = self.get_submit_json(
            opt_in_hours=None,
            timezone=None,
            comments=None,
        )
        response = self.client.post(protected_url_for('volunteers.submit'), json=data)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(Submission.query.count(), 1)
        self.assertEqual(Volunteer.query.count(), 0)

        submission = Submission.query.first()

        self.assertEqual(submission.name, 'Test User')
        self.assertEqual(submission.email, 'test-user@example.com')
        self.assertEqual(submission.phone_number, '+14169671111')
        self.assertEqual(submission.opt_in_hours, [])
        self.assertEqual(submission.comments, '')
        self.assertEqual(submission.timezone, '')
        self.assertTrue(submission.enabled)

        # We had no time slots, so this is the same as disabled. Don't call.
        self.twilio_mock.calls.create.assert_not_called()

        data = self.get_submit_json(
            opt_in_hours=['noon' - '2pm'],
            timezone=None,
            comments=None,
        )
        response = self.client.post(protected_url_for('volunteers.submit'), json=data)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(Submission.query.count(), 2)
        self.assertEqual(Volunteer.query.count(), 0)

        submission = Submission.query.order_by(Submission.id.desc()).first()

        self.assertEqual(submission.name, 'Test User')
        self.assertEqual(submission.email, 'test-user@example.com')
        self.assertEqual(submission.phone_number, '+14169671111')
        self.assertEqual(submission.opt_in_hours, [12, 13])
        self.assertEqual(submission.comments, '')
        self.assertEqual(submission.timezone, '')
        self.assertTrue(submission.enabled)

        self.twilio_mock.calls.create.assert_called_once_with(
            from_=app.config['WEIRDNESS_NUMBER'],
            to='+14169671111',
            url=protected_url_for('volunteers.verify', id=submission.id),
        )

    def test_create_or_update_volunteer(self):
        self.assertEqual(Submission.query.count(), 0)
        self.assertEqual(Volunteer.query.count(), 0)

        # Create
        submission1 = self.create_submission()
        volunteer = submission1.create_or_update_volunteer()

        self.assertEqual(Submission.query.count(), 1)
        self.assertEqual(Volunteer.query.count(), 1)

        self.assertEqual(submission1.name, volunteer.name)
        self.assertEqual(submission1.email, volunteer.email)
        self.assertEqual(submission1.phone_number, volunteer.phone_number)
        self.assertEqual(submission1.opt_in_hours, volunteer.opt_in_hours)
        self.assertEqual(submission1.comments, volunteer.comments)
        self.assertEqual(submission1.id, volunteer.submission_id)
        previous_id = volunteer.id

        # Update
        submission2 = self.create_submission(
            name='Updated User',
            email='updated@example.com',
            opt_in_hours=list(range(12, 18)),
            comments='updated',
        )
        volunteer = submission2.create_or_update_volunteer()

        self.assertEqual(Submission.query.count(), 2)
        self.assertEqual(Volunteer.query.count(), 1)

        self.assertEqual(previous_id, volunteer.id)
        self.assertEqual(submission2.name, volunteer.name)
        self.assertEqual(submission2.email, volunteer.email)
        self.assertEqual(submission2.phone_number, volunteer.phone_number)
        self.assertEqual(submission2.opt_in_hours, volunteer.opt_in_hours)
        self.assertEqual(submission2.comments, volunteer.comments)
        self.assertEqual(submission2.id, volunteer.submission_id)

        # Delete
        submission3 = self.create_submission(enabled=False)
        volunteer = submission3.create_or_update_volunteer()

        self.assertIsNone(volunteer)
        self.assertEqual(Submission.query.count(), 3)
        self.assertEqual(Volunteer.query.count(), 0)

        # Delete again, should do nothing
        submission4 = self.create_submission(enabled=False)
        volunteer = submission4.create_or_update_volunteer()

        self.assertEqual(Submission.query.count(), 4)
        self.assertEqual(Volunteer.query.count(), 0)

    def test_json_view(self):
        submissions = [
            self.create_submission(phone_number='+1416967111{}'.format(n))
            for n in range(5)
        ]
        volunteers = [s.create_or_update_volunteer() for s in submissions]
        data = {'submissions': submissions, 'volunteers': volunteers}

        response = self.client.get(protected_url_for('volunteers.json'))
        self.assertEqual(response.status_code, 200)

        for key, items in data.items():
            self.assertIn(key, response.json)
            self.assertEqual(len(response.json[key]), len(items))
            self.assertCountEqual(
                [item.id for item in items],
                [item['id'] for item in response.json[key]])
        self.assertEqual(response.json['timezone'], 'US/Pacific')
