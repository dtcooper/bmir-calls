import os
import pprint

from twilio.base.exceptions import TwilioRestException

from flask import request

from calls.models import (
    db,
    Submission,
    UserConfig,
    Volunteer,
)
from calls.utils import sanitize_phone_number


def register_commands(app):
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

    @app.cli.add_command
    @app.cli.command('sms-blast', help='Blast volunteers with an SMS')
    def sms_blast():
        from calls.models import Volunteer

        with app.app_context():
            print('Environment: {}'.format(app.config['ENV']))
            print(' Volunteers: {}'.format(Volunteer.query.count()))
            print()

            body = input('What is your SMS (add \\n for newline)? ').replace('\\n', '\n').strip()
            if not body:
                print('Nothing entered.')
                return

            print(' {}/160 chars '.format(len(body)).center(60, '='))
            print(body)
            print('=' * 60)
            if not input('Are you sure (y/n)? ').strip().lower().startswith('y'):
                print('Aborting.')
                return

            volunteers = Volunteer.query.order_by(Volunteer.id).all()

            for n, volunteer in enumerate(volunteers, 1):
                try:
                    app.twilio.messages.create(
                        body=body, from_=app.config['WEIRDNESS_NUMBER'],
                        to=volunteer.phone_number)
                    failed = False
                except TwilioRestException:
                    failed = True
                print('{}/{}: {}{}'.format(
                    n, len(volunteers), volunteer.phone_number, ' FAILED!' if failed else ''))

    @app.shell_context_processor
    def extra_shell_variables():
        return {'db': db, 'Submission': Submission, 'UserConfig': UserConfig,
                'Volunteer': Volunteer, 'sanitize_phone_number': sanitize_phone_number}

    if app.debug and os.environ.get('PRINT_REQUESTS'):  # skip coverage
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
