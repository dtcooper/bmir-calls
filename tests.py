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
    UserCodeConfig,
    Volunteer,
)


class BMIRCallsTests(unittest.TestCase):
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
            'BROADCAST_SIP_USERNAME': 'broadcast',
            'TWILIO_SIP_DOMAIN': 'domain',
            'WEIRDNESS_SIP_USERNAME': 'weirdness',
            'WEIRDNESS_SIP_ALT_USERNAMES': {'weirdness-alt1', 'weirdness-alt2'}
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
            'phone_number': '416-967-1111',
            'opt_in_hours': ['midnight - 3am', '3am - 6am', '6am - 9am', '9am - noon',
                             'noon - 3pm', '3pm - 6pm', '6pm - 9pm', '9pm - midnight'],
            'timezone': '[GMT-07:00] Pacific Time // Black Rock City Time (US/Pacific)',
        }
        json_data.update(kwargs)

        mock_phone = '+1{}'.format(re.sub(r'[^0-9]', '', json_data['phone_number']))
        self.twilio_mock.lookups.phone_numbers().fetch().phone_number = mock_phone

        return json_data

    @staticmethod
    def create_submission(**kwargs):
        defaults = {
            'timezone': '[GMT-07:00] Pacific Time // Black Rock City Time (US/Pacific)',
            'phone_number': '+14169671111',
            'opt_in_hours': list(range(24)),
            'valid_phone': True,
        }
        defaults.update(kwargs)
        submission = Submission(**defaults)
        db.session.add(submission)
        db.session.commit()
        return submission

    @classmethod
    def create_volunteer(cls, submission=None):
        if not submission:
            submission = cls.create_submission()
        return submission.create_volunteer()

    def test_form_submit(self):
        self.assertEqual(Submission.query.count(), 0)
        self.assertEqual(Volunteer.query.count(), 0)

        response = self.client.post(
            url_for('volunteers.submit'), json=self.get_submit_json())
        self.assertEqual(response.status_code, 200)

        self.assertEqual(Submission.query.count(), 1)
        self.assertEqual(Volunteer.query.count(), 0)

        submission = Submission.query.first()
        self.assertEqual(submission.phone_number, '+14169671111')
        self.assertEqual(submission.opt_in_hours, list(range(24)))
        self.assertEqual(
            submission.timezone,
            '[GMT-07:00] Pacific Time // Black Rock City Time (US/Pacific)',
        )
        self.assertTrue(submission.valid_phone)
        self.assertEqual(self.twilio_mock.calls.create.call_count, 1)

    def test_form_submit_additional_cases(self):
        # Empty timezone, minimal opt in
        response = self.client.post(
            url_for('volunteers.submit'),
            json=self.get_submit_json(opt_in_hours=['midnight - 3am'], timezone=None))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(Submission.query.count(), 1)
        self.assertEqual(Volunteer.query.count(), 0)
        submission = Submission.query.first()
        self.assertEqual(submission.phone_number, '+14169671111')
        self.assertEqual(submission.opt_in_hours, [0, 1, 2])
        self.assertEqual(submission.timezone, '')
        self.assertEqual(self.twilio_mock.calls.create.call_count, 1)
        self.assertEqual(self.twilio_mock.messages.create.call_count, 0)

        # Invalid phone number, nothing happens
        with patch('calls.models.sanitize_phone_number', lambda _: False):
            response = self.client.post(
                url_for('volunteers.submit'),
                json=self.get_submit_json(phone_number='hi mom!'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.query.count(), 2)
        self.assertEqual(Volunteer.query.count(), 0)
        submission = Submission.query.order_by(Submission.id.desc()).first()
        self.assertFalse(submission.valid_phone)
        self.assertEqual(self.twilio_mock.calls.create.call_count, 1)
        self.assertEqual(self.twilio_mock.messages.create.call_count, 0)

        # Now let's create a volunteer with the same phone number
        submission = self.create_submission()
        volunteer = submission.create_volunteer()
        self.assertEqual(volunteer.opt_in_hours, list(range(24)))
        self.assertEqual(Submission.query.count(), 3)
        self.assertEqual(Volunteer.query.count(), 1)

        # Volunteer exists, we update and text them
        response = self.client.post(
            url_for('volunteers.submit'),
            json=self.get_submit_json(opt_in_hours=['noon - 3pm'], timezone='invalid'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.query.count(), 4)
        self.assertEqual(Volunteer.query.count(), 1)
        volunteer = Volunteer.query.first()
        self.assertEqual(volunteer.opt_in_hours, [12, 13, 14])
        self.assertEqual(self.twilio_mock.calls.create.call_count, 1)
        self.assertEqual(self.twilio_mock.messages.create.call_count, 1)

    def test_column_max_size(self):
        submission = self.create_submission(phone_number='1' * 500)
        self.assertEqual(len(submission.phone_number), 20)

    def test_verify(self):
        submission = self.create_submission()
        self.assertEqual(Volunteer.query.count(), 0)

        # Initial TwiML
        response = self.client.post(url_for('volunteers.verify', id=submission.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Volunteer.query.count(), 0)

        # Answered by machine
        response = self.client.post(
            url_for('volunteers.verify', id=submission.id),
            data={'AnsweredBy': 'machine_start'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Volunteer.query.count(), 0)

        # User pressed '1', Create new volunteer (and test invalid gather arg)
        response = self.client.post(
            url_for('volunteers.verify', id=submission.id, gather='q'),
            data={'Digits': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Volunteer.query.count(), 1)

        volunteer = Volunteer.query.first()
        self.assertEqual(submission.id, volunteer.submission_id)
        self.assertEqual(submission.phone_number, volunteer.phone_number)
        self.assertEqual(submission.opt_in_hours, volunteer.opt_in_hours)

        # Try to verify a submission with the same phone number fails
        submission_dupe = self.create_submission()
        response = self.client.post(
            url_for('volunteers.verify', id=submission_dupe.id),
            data={'Digits': '1'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Volunteer.query.count(), 1)

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
        self.assertIn(
            b'There are forty people in this world, and five of them are hamburgers.',
            response.data)

        response = self.client.get(url_for('form_redirect'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, app.config['WEIRDNESS_SIGNUP_GOOGLE_FORM_URL'])

    def test_protection(self):
        protected_routes = (
            # route, method, kwargs
            ('outgoing', 'post', {}),
            ('broadcast.incoming', 'post', {}),
            ('broadcast.sms', 'post', {}),
            ('volunteers.submit', 'post', {}),
            ('volunteers.verify', 'get', {'id': 1}),
            ('volunteers.verify', 'post', {'id': 1}),
            ('volunteers.json', 'get', {}),
            ('weirdness.outgoing', 'post', {}),
            ('weirdness.whisper', 'post', {}),
            ('weirdness.incoming', 'post', {}),
            ('weirdness.sms', 'post', {}),
        )

        try:
            app.config['API_PASSWORD'] = 'my-secret-password'

            for route, method, kwargs in protected_routes:
                response = getattr(self.client, method)(url_for(
                    route, password='incorrect', **kwargs))
                self.assertEqual(
                    response.status_code, 403,
                    '{} returned a {}'.format(route, response.status_code))

        finally:
            app.config['API_PASSWORD'] = ''

    def test_weirdness_whisper(self):
        response = self.client.post(url_for('weirdness.whisper'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Incoming call', response.data)

    def test_outgoing_unknown_sip_addr(self):
        response = self.client.post(
            url_for('outgoing'), data={'From': 'sip:unknown@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid SIP address.', response.data)

    @patch('random.randint')
    def test_broadcast_outgoing(self, randint):
        # Invalid number
        self.twilio_mock.lookups.phone_numbers().fetch().phone_number = None
        response = self.client.post(
            url_for('outgoing'),
            data={'From': 'sip:broadcast@domain', 'To': 'sip:0114169671111@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your call cannot be completed as dialed.', response.data)
        response = self.client.post(
            url_for('outgoing'), data={'From': 'sip:broadcast@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your call cannot be completed as dialed.', response.data)

        # Outgoing number
        self.twilio_mock.lookups.phone_numbers().fetch().phone_number = '+14169671111'
        response = self.client.post(
            url_for('outgoing'),
            data={'From': 'sip:broadcast@domain', 'To': 'sip:0014169671111@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'+14169671111', response.data)

        # ## (double pound) cheat code routes to weirdness phone outside
        response = self.client.post(
            url_for('outgoing'),
            data={'From': 'sip:broadcast@domain', 'To': 'sip:%23%23@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'weirdness@domain', response.data)

        # * cheat code, routes to Volunteer
        self.create_volunteer()
        response = self.client.post(
            url_for('outgoing'),
            data={'From': 'sip:broadcast@domain', 'To': 'sip:*@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'+14169671111', response.data)

        # Since we're broadcast outgoing, no random shuffle here
        randint.assert_not_called()

    def test_broadcast_user_code_config(self):
        for code in UserCodeConfig.CODES:
            # Toggle each code
            for value in (code.default, not code.default):
                self.assertEqual(UserCodeConfig.get(code.name), value)
                response = self.client.post(
                    url_for('outgoing'), data={'From': 'sip:broadcast@domain',
                                               'To': 'sip:%23{}@domain'.format(code.number)})
                self.assertEqual(response.status_code, 200)
                self.assertIn('{} is now {}.'.format(
                    code.description, 'disabled' if value else 'enabled').encode(),
                    response.data)
                self.assertEqual(UserCodeConfig.get(code.name), not value)

        self.assertIsNone(UserCodeConfig.get('invalid_code_name'))
        response = self.client.post(
            url_for('outgoing'), data={'From': 'sip:broadcast@domain',
                                       'To': 'sip:%239@domain'.format(code.number)})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid code. Please try again.', response.data)
        self.assertIsNone(UserCodeConfig.get('invalid_code_name'))

    def test_broadcast_incoming(self):
        # Test basic incoming
        response = self.client.post(url_for('broadcast.incoming'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'broadcast@domain', response.data)

        # Not answering / busy go to voice mail
        for status in ('busy', 'no-answer', 'failed'):
            response = self.client.post(url_for('broadcast.incoming'),
                                        data={'DialCallStatus': status})
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'<Record', response.data)

        # Call completed hangs up (trolls with jingle)
        response = self.client.post(url_for('broadcast.incoming'),
                                    data={'DialCallStatus': 'completed'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<Play', response.data)

        # Ringer turned off
        UserCodeConfig.set('broadcast_incoming', False)
        response = self.client.post(url_for('broadcast.incoming'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<Record', response.data)

    def test_broadcast_sms(self):
        response = self.client.post(url_for('broadcast.sms'))
        self.assertEqual(response.status_code, 501)

    @patch('random.randint')
    def test_weirdness_outgoing(self, randint):
        randint.return_value = 2  # Don't call broadcast

        # No volunteers
        response = self.client.post(
            url_for('outgoing'), data={'From': 'sip:weirdness@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Thanks for playing!', response.data)

        # With a volunteer
        volunteer = self.create_volunteer()
        self.assertIsNone(volunteer.last_called)
        response = self.client.post(
            url_for('outgoing'), data={'From': 'sip:weirdness@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'+14169671111', response.data)
        self.assertIsNotNone(volunteer.last_called)

        # Hung up on, 30s after a call (alternate phone)
        response = self.client.post(
            url_for('outgoing'),
            data={'From': 'sip:weirdness-alt1@domain',
                  'DialCallStatus': 'completed', 'DialCallDuration': '60'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Microsoft Zune', response.data)

        # Randomly calls broadcast phone (other alternate)
        randint.return_value = 1
        UserCodeConfig.set('random_weirdness_to_broadcast', True)
        response = self.client.post(
            url_for('outgoing'), data={'From': 'sip:weirdness-alt2@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'broadcast@domain', response.data)

        # Unless broadcast phone is disabled
        UserCodeConfig.set('random_weirdness_to_broadcast', False)
        response = self.client.post(
            url_for('outgoing'), data={'From': 'sip:weirdness@domain'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'+14169671111', response.data)

    def test_weirdness_incoming(self):
        # Unknown number
        self.twilio_mock.lookups.phone_numbers().fetch().phone_number = None
        response = self.client.post(url_for('weirdness.incoming'),
                                    data={'From': '+15555551234'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Call with your caller ID unblocked to get through', response.data)

        self.twilio_mock.lookups.phone_numbers().fetch().phone_number = '+14164390000'

        # First run through of menu
        response = self.client.post(
            url_for('weirdness.incoming'), data={'From': '14164390000'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'You are not currently enrolled.', response.data)

        # Second run through minimal <Say>
        response = self.client.post(url_for('weirdness.incoming', gather=1),
                                    data={'From': '14164390000'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'You are not currently enrolled.', response.data)

        # Press 1, which redirects to volunteers.verify
        self.assertEqual(Submission.query.count(), 0)
        response = self.client.post(url_for('weirdness.incoming'),
                                    data={'From': '14164390000', 'Digits': '1'})
        self.assertEqual(Submission.query.count(), 1)
        submission = Submission.query.first()
        self.assertEqual(submission.phone_number, '+14164390000')
        self.assertEqual(response.status_code, 302)
        self.assertIn(url_for('volunteers.verify', id=submission.id), response.location)
        self.assertIn('phoned=y', response.location)

        self.create_volunteer(submission)

        # Now we call already as a volunteer, and press 1
        response = self.client.post(url_for('weirdness.incoming'),
                                    data={'From': '+14164390000', 'Digits': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Press 1 to confirm you would like to stop receiving calls.',
                      response.data)
        self.assertEqual(Volunteer.query.count(), 1)

        # Now delete
        response = self.client.post(url_for('weirdness.incoming', confirm='y'),
                                    data={'From': '+14164390000', 'Digits': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'You will no longer receive calls.', response.data)
        self.assertEqual(Volunteer.query.count(), 0)

    def test_weirdness_sms(self):
        # Unknown number
        response = self.client.post(url_for('weirdness.sms'), data={'Body': 'hi'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Go to https://calls.bmir.org/ to sign up for BMIR Phone Experiment.',
                      response.data)

        self.twilio_mock.lookups.phone_numbers().fetch().phone_number = '+14164390000'

        # Message for non-enrolled number
        response = self.client.post(url_for('weirdness.sms'),
                                    data={'Body': 'hi', 'From': '4164390000'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'SIGN UP', response.data)
        self.assertIn(b'to sign up', response.data)

        # Sign up non-enrolled number
        self.assertEqual(Volunteer.query.count(), 0)
        response = self.client.post(url_for('weirdness.sms'),
                                    data={'Body': 'siGn  uP', 'From': '4164390000'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'You have signed up', response.data)
        self.assertIn(b'GO AWAY', response.data)
        self.assertEqual(Volunteer.query.count(), 1)
        volunteer = Volunteer.query.first()
        self.assertEqual(volunteer.phone_number, '+14164390000')

        # Text as enrolled number
        response = self.client.post(url_for('weirdness.sms'),
                                    data={'Body': 'hi', 'From': '4164390000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Volunteer.query.count(), 1)
        self.assertIn(b'GO AWAY', response.data)
        self.assertIn(b'to stop receiving', response.data)

        # Now unenroll
        response = self.client.post(url_for('weirdness.sms'),
                                    data={'Body': 'go AWAY', 'From': '4164390000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Volunteer.query.count(), 0)
        self.assertIn(b'You will no longer receive calls', response.data)
        self.assertIn(b'SIGN UP', response.data)
