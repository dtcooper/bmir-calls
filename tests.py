import re
from unittest.mock import patch
import unittest

import pytz
from sqlalchemy.engine.url import make_url

from flask import url_for

from calls import app
from calls.models import (
    db,
    Submission,
    Volunteer,
)


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
            'API_PASSWORD': '',
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

    def get_submit_json(self, **kwargs):
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
            url_for('volunteers.submit'), json=self.get_submit_json())
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
        self.assertEqual(self.twilio_mock.calls.create.call_count, 1)

    def test_form_submit_additional_cases(self):
        # Try 1: Empty values
        response = self.client.post(
            url_for('volunteers.submit'),
            json=self.get_submit_json(opt_in_hours=None, timezone=None, comments=None))
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
        self.assertEqual(self.twilio_mock.calls.create.call_count, 0)
        self.assertEqual(self.twilio_mock.messages.create.call_count, 1)

        # Try 2: We have time slots, but now we're disabled
        response = self.client.post(
            url_for('volunteers.submit'),
            json=self.get_submit_json(opt_in_hours=['noon - 2pm'], enabled=False))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.query.count(), 2)
        self.assertEqual(Volunteer.query.count(), 0)
        self.assertEqual(self.twilio_mock.calls.create.call_count, 0)
        self.assertEqual(self.twilio_mock.messages.create.call_count, 2)

        # Try 3: Invalid phone number, nothing happens
        with patch('calls.models.sanitize_phone_number', lambda _: False):
            response = self.client.post(
                url_for('volunteers.submit'),
                json=self.get_submit_json(phone_number='hi mom!'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.query.count(), 3)
        self.assertEqual(Volunteer.query.count(), 0)
        submission = Submission.query.order_by(Submission.id.desc()).first()
        self.assertFalse(submission.valid_phone)
        self.assertEqual(self.twilio_mock.calls.create.call_count, 0)
        self.assertEqual(self.twilio_mock.messages.create.call_count, 2)

        # Now let's create a volunteer with the same phone number
        submission = self.create_submission()
        volunteer = submission.create_volunteer()
        self.assertNotEqual(volunteer.name, 'Updated User')
        self.assertEqual(Submission.query.count(), 4)
        self.assertEqual(Volunteer.query.count(), 1)

        # Try 4: Volunteer exists
        response = self.client.post(
            url_for('volunteers.submit'),
            json=self.get_submit_json(name='Updated User', timezone='invalid'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.query.count(), 5)
        self.assertEqual(Volunteer.query.count(), 1)
        volunteer = Volunteer.query.first()
        self.assertEqual(volunteer.name, 'Updated User')
        self.assertEqual(self.twilio_mock.calls.create.call_count, 0)
        self.assertEqual(self.twilio_mock.messages.create.call_count, 3)

        # Try 5: Disable
        response = self.client.post(
            url_for('volunteers.submit'), json=self.get_submit_json(enabled=False))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.query.count(), 6)
        self.assertEqual(Volunteer.query.count(), 0)
        self.assertEqual(self.twilio_mock.calls.create.call_count, 0)
        self.assertEqual(self.twilio_mock.messages.create.call_count, 4)

    def test_column_max_size(self):
        submission = self.create_submission(
            name='a' * 500,
            phone_number='1' * 500,
            email='a@{}.com'.format('b' * 500),
        )

        self.assertEqual(len(submission.name), 255)
        self.assertEqual(len(submission.email), 255)
        self.assertEqual(len(submission.phone_number), 20)

    def test_json_view(self):
        submissions = [
            self.create_submission(phone_number='+1416967111{}'.format(n))
            for n in range(5)
        ]
        volunteers = [s.create_volunteer() for s in submissions]
        data = {'submissions': submissions, 'volunteers': volunteers}

        response = self.client.get(url_for('volunteers.json'))
        self.assertEqual(response.status_code, 200)

        for key, items in data.items():
            self.assertIn(key, response.json)
            self.assertEqual(len(response.json[key]), len(items))
            self.assertCountEqual(
                [item.id for item in items],
                [item['id'] for item in response.json[key]])
        self.assertEqual(response.json['timezone'], 'US/Pacific')

    def test_public_urls(self):
        response = self.client.get(url_for('health'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(url_for('form_redirect'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, app.config['WEIRDNESS_SIGNUP_GOOGLE_FORM_URL'])
