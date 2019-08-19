import datetime

import pytz


SERVER_TZ = pytz.timezone('US/Pacific')

# No known daylight savings changes in August, so let's pick a date during BM
DATE_FOR_TZ_CONVERSION = datetime.date(2019, 8, 25)
FORM_HOUR_CHUNK_SIZE = 3

VOLUNTEER_RANDOM_POOL_SIZE = 5
MULTIRING_COUNT = 3
WEIRDNESS_RANDOM_CHANCE_OF_RINGING_BROADCAST = 50
INCOMING_CALLERS_RANDOM_CHANCE_OF_WEIRDNESS = 15

MAX_PANEL_ITEMS = 50
SERIALIZE_STRFTIME = '%a %b %d %I:%M:%S %p'
