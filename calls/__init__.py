import os
import random

from twilio.rest import Client as TwilioClient
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import (
    Flask,
    redirect,
    request,
    url_for,
)

from calls import commands
from calls.models import db
from calls.utils import (
    parse_sip_address,
    protected,
    render_xml,
)
from calls.views import (
    broadcast,
    outgoing_broadcast,
    outgoing_weirdness,
    volunteers,
    weirdness,
)


# Set up Flask app
app = Flask(__name__)
BASE_DIR = os.path.dirname(__file__)

# Load config files
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.from_pyfile(os.path.join(BASE_DIR, 'base_config.py'))
site_config_path = os.path.join(BASE_DIR, '..', 'config.py')
if os.path.exists(site_config_path):  # skip coverage
    app.config.from_pyfile(site_config_path)

# Register extensions
db.init_app(app)
commands.register_commands(app)

# Set up Twilio client globally on app
app.twilio = TwilioClient(
    app.config['TWILIO_ACCOUNT_SID'],
    app.config['TWILIO_AUTH_TOKEN'],
)

# Register blueprints
app.register_blueprint(broadcast)
app.register_blueprint(volunteers)
app.register_blueprint(weirdness)

# Make sure reverse proxying from an https URL to http is considered secure.
# Gunicorn does this automatically, but Flask's development server does not.
if app.debug:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


SONGS = os.listdir(os.path.join(BASE_DIR, 'static', 'songs'))


@app.context_processor
def extra_template_context():
    return {
        'song_url': url_for('static', filename='songs/{}'.format(
            random.choice(SONGS)), _external=True),
        'recording_enabled_globally': app.config['RECORDING_ENABLED'],
    }


@app.route('/health')
def health():
    return 'There are forty people in this world, and five of them are hamburgers.'


@app.route('/')
def form_redirect():
    return redirect(app.config['WEIRDNESS_SIGNUP_GOOGLE_FORM_URL'])


# SIP domains on Twilio route to the same URL, so basic routing done here
@app.route('/outgoing', methods=('POST',))
@protected
def outgoing():
    from_address = parse_sip_address(request.values.get('From'))
    if from_address == app.config['BROADCAST_SIP_USERNAME']:
        return outgoing_broadcast()
    elif (
        from_address == app.config['WEIRDNESS_SIP_USERNAME']
        or from_address in app.config['WEIRDNESS_SIP_ALT_USERNAMES']
    ):
        return outgoing_weirdness()
    else:
        return render_xml('hang_up.xml', message='Invalid SIP address.')
