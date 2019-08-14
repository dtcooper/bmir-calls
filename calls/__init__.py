import os

from twilio.rest import Client as TwilioClient
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import (
    Flask,
    redirect,
    request,
)

from calls.models import db
from calls.views import (
    call_routing,
    volunteers,
)


# Set up Flask app
app = Flask(__name__)

# Load config files
app.config.from_pyfile(os.path.join(os.path.dirname(__file__), 'base_config.py'))
site_config_path = os.path.join(os.path.dirname(__file__), '..', 'config.py')
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
app.register_blueprint(call_routing)
app.register_blueprint(volunteers)

# Make sure reverse proxying from an https URL to http is considered secure.
# Gunicorn does this automatically, but Flask's development server does not.
if app.debug:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


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


@app.route('/health')
def health():
    return 'There are forty people in this world, and five of them are hamburgers.'


@app.route('/')
def form_redirect():
    return redirect(app.config['WEIRDNESS_SIGNUP_GOOGLE_FORM_URL'])


if app.debug and os.environ.get('PRINT_REQUESTS'):  # skip coverage
    @app.before_request
    def before():
        print(request.headers)
        import pprint
        pprint.pprint(request.values)

    @app.after_request
    def after(response):
        print(response.status)
        print(response.headers)
        print(response.get_data().decode('utf-8'))
        return response
