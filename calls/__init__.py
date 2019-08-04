import os

from twilio.rest import Client as TwilioClient
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import Flask

from .models import db


# Set up Flask app
app = Flask(__name__)

# Read config defaults and local config.py file
app.config.from_pyfile(os.path.join(os.path.dirname(__file__), 'config.py'))
site_config_path = os.path.join(os.path.dirname(__file__), '..', 'config.py')
if os.path.exists(site_config_path):
    app.config.from_pyfile(site_config_path)

# Set up DB
db.init_app(app)

# Set up Twilio client globally on app
app.twilio = TwilioClient(
    app.config['TWILIO_ACCOUNT_SID'],
    app.config['TWILIO_AUTH_TOKEN'],
)

# Make sure reverse proxying from an https URL to http is considered secure.
# Gunicorn does this automatically, but Flask's development server does not.
if app.config['DEBUG']:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


# No public routes!
@app.route('/')
def index():
    return 'There are forty people in this world, and five of them are hamburgers.'
