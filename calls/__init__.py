import os

from twilio.rest import Client as TwilioClient
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import (
    Flask,
    request,
    Response,
)

from .models import db
from .volunteers import volunteers


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
app.register_blueprint(volunteers)

# Make sure reverse proxying from an https URL to http is considered secure.
# Gunicorn does this automatically, but Flask's development server does not.
if app.config['DEBUG']:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config['SESSION_COOKIE_SECURE'] = False


@app.cli.add_command
@app.cli.command('init-db', help='Initialize the DB.')
def init_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
        db.session.commit()


@app.before_request
def protected():
    password = request.args.get('password', '')
    if not (password == app.config['API_PASSWORD'] or app.config['DEBUG']):
        return Response(status=403)


@app.route('/')
def index():
    return 'There are forty people in this world, and five of them are hamburgers.'
