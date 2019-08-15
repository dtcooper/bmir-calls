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
app.config.from_pyfile(os.path.join(BASE_DIR, 'base_config.py'))
site_config_path = os.path.join(BASE_DIR, '..', 'config.py')
if os.path.exists(site_config_path):
    app.config.from_pyfile(site_config_path)

# Register extensions
db.init_app(app)


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
    return {'song_url': url_for(
        'static', filename='songs/{}'.format(random.choice(SONGS)), _external=True)}


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


@app.cli.add_command
@app.cli.command('init-db', help='Initialize the DB.')
def init_db():
    with app.app_context():
        if app.config['ENV'] != 'development':
            confirm = input('Your flask environment is {}. Are you sure '
                            '(y/n)? '.format(app.config['ENV']))
            if not confirm.strip().lower().startswith('y'):
                print('Aborting.')
                return

        db.drop_all()
        db.create_all()
        db.session.commit()


@app.shell_context_processor
def extra_shell_variables():
    from calls.models import Submission, UserConfig, Volunteer
    from calls.utils import sanitize_phone_number
    return {'db': db, 'Submission': Submission, 'UserConfig': UserConfig,
            'Volunteer': Volunteer, 'sanitize_phone_number': sanitize_phone_number}


if app.debug and os.environ.get('PRINT_REQUESTS'):  # skip coverage
    import pprint

    @app.before_request
    def before():
        print(request.headers)
        pprint.pprint(request.values)

    @app.after_request
    def after(response):
        print(response.status)
        print(response.headers)
        print(response.get_data().decode('utf-8'))
        return response
