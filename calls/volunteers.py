from flask import (
    Blueprint,
    current_app as app,
    request,
    Response,
    url_for,
)

from .models import (
    db,
    Submission,
    Volunteer,
)
from .utils import (
    protected,
    protected_external_url,
    render_xml,
)


volunteers = Blueprint('volunteers', __name__, url_prefix='/volunteers')


def process_submit(submission):
    if not submission.valid_phone:
        return

    text_msg = None
    form_redirect_url = url_for('form_redirect', _external=True)

    # Do we already have a volunteer?
    volunteer = Volunteer.query.filter_by(
        phone_number=submission.phone_number).first()

    # A volunteer already exists for this phone number
    if volunteer:
        if submission.enabled and submission.opt_in_hours:
            text_msg = 'Thanks for updating your submission.'
            for attr, value in submission.get_volunteer_kwargs().items():
                setattr(volunteer, attr, value)
            db.session.add(volunteer)
        else:
            text_msg = ('You will no longer receive calls. To sign back up, go '
                        'to: {}'.format(form_redirect_url))
            db.session.delete(volunteer)
        db.session.commit()
    else:
        if submission.enabled and submission.opt_in_hours:
            app.twilio.calls.create(
                url=protected_external_url('volunteers.verify', id=submission.id),
                from_=app.config['WEIRDNESS_NUMBER'],
                to=submission.phone_number,
            )

        else:
            text_msg = 'You will NOT receive calls. '

            if not submission.enabled:
                text_msg += 'Select "YES" to "Do you want to receive calls?"'
            else:
                text_msg += 'You must select hours under "Call me ONLY at these times"'

            text_msg += ' Try again: {}'.format(form_redirect_url)

    if text_msg:
        app.twilio.messages.create(
            body='{}\n-BMIR Phone Experiment'.format(text_msg),
            from_=app.config['WEIRDNESS_NUMBER'],
            to=submission.phone_number,
        )


@volunteers.route('/submit', methods=('POST',))
@protected
def submit():
    submission = Submission.create_from_json(request.get_json())
    process_submit(submission)
    return Response(status=200)


@volunteers.route('/submit/verify/<int:id>', methods=('POST', 'GET'))
@protected
def verify(id):
    submission = Submission.query.filter_by(id=id).first_or_404()
    reject = confirmed = False

    try:
        gather_times = int(request.args.get('gather', '0'), 10) + 1
    except ValueError:
        gather_times = 1

    if request.values.get('Digits') == '1':
        if not submission.create_volunteer():
            return Response(status=409)  # Conflict
        confirmed = True
    else:
        reject = gather_times > 6

    return render_xml(
        'volunteers/verify.xml',
        action_url=protected_external_url(
            'volunteers.verify', id=submission.id, gather=gather_times),
        confirmed=confirmed,
        first_run=gather_times == 1,
        name=submission.name,
        reject=reject,
        song_url=app.config['WEIRDNESS_SIGNUP_SONG'],
    )


@volunteers.route('/')
@protected
def json():
    return {
        'submissions': [s.serialize() for s in Submission.query.order_by(
            Submission.id.desc()).all()],
        'volunteers': [v.serialize() for v in Volunteer.query.order_by(
            Volunteer.id.desc()).all()],
        'timezone': str(app.config['SERVER_TZ'].zone),
    }
