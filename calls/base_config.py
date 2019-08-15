import datetime

import pytz


API_PASSWORD = 'hackme'

SQLALCHEMY_DATABASE_URI = 'postgresql://postgres@db/'
SQLALCHEMY_DATABASE_NAME_TESTING = 'testing'
SQLALCHEMY_TRACK_MODIFICATIONS = False

TWILIO_ACCOUNT_SID = 'ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
TWILIO_AUTH_TOKEN = 'hackme'

SERVER_TZ = pytz.timezone('US/Pacific')
# No known daylight savings changes in August, so let's pick a date during BM
DATE_FOR_TZ_CONVERSION = datetime.date(2019, 8, 25)
FORM_HOUR_CHUNK_SIZE = 3

TWILIO_SIP_DOMAIN = 'example.sip.us1.twilio.com'

BROADCAST_NUMBER = '+15555554321'
BROADCAST_SIP_USERNAME = 'broadcast'

WEIRDNESS_SIGNUP_GOOGLE_FORM_URL = 'http://example.com/'
WEIRDNESS_NUMBER = '+15555551234'
WEIRDNESS_SIP_USERNAME = 'weirdness'
WEIRDNESS_SIP_ALT_USERNAMES = {'weirdness-alt1', 'weirdness-alt2'}
