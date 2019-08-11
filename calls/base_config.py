import datetime

import pytz


API_PASSWORD = 'hackme'

SQLALCHEMY_DATABASE_URI = 'postgresql://postgres@db/'
SQLALCHEMY_DATABASE_NAME_TESTING = 'testing'
SQLALCHEMY_TRACK_MODIFICATIONS = False

TWILIO_ACCOUNT_SID = 'ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
TWILIO_AUTH_TOKEN = 'hackme'

SERVER_TZ = pytz.timezone('US/Pacific')
# No known conversions in August, so let's pick a date during the event
DATE_FOR_TZ_CONVERSION = datetime.date(2019, 8, 25)
FORM_HOUR_CHUNK_SIZE = 3

BROADCAST_NUMBER = '+15555554321'
BROADCAST_SIP_USERNAME = 'broadcast'

WEIRDNESS_SIGNUP_GOOGLE_FORM_URL = 'http://example.com/'
WEIRDNESS_SIGNUP_MUSIC = 'http://example.com/singup-song.mp3'
WEIRDNESS_NUMBER = '+15555551234'
WEIRDNESS_SIP_USERNAME = 'weirdness'
