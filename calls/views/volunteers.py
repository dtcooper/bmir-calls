from flask import (
    Blueprint,
    current_app as app,
    request,
    Response,
)

from calls.models import (
    db,
    Submission,
    Volunteer,
)
from calls.utils import (
    get_gather_times,
    external_url,
    protected,
    protected_external_url,
    render_xml,
)


volunteers = Blueprint('volunteers', __name__, url_prefix='/volunteers')


@volunteers.route('/submit', methods=('POST',))
@protected
def submit():
    submission = Submission.create_from_json(request.get_json())

    if submission.valid_phone:
        # Do we already have a volunteer?
        volunteer = Volunteer.query.filter_by(
            phone_number=submission.phone_number).first()

        # A volunteer already exists for this phone number
        if volunteer:
            for attr, value in submission.get_volunteer_kwargs().items():
                setattr(volunteer, attr, value)

            db.session.add(volunteer)
            db.session.commit()

            app.twilio.messages.create(
                body='Thanks for updating your BMIR Phone Experiment submission.',
                from_=app.config['WEIRDNESS_NUMBER'],
                to=submission.phone_number,
            )

        else:
            app.twilio.calls.create(
                machine_detection='Enable',
                machine_detection_silence_timeout=3000,
                url=protected_external_url('volunteers.verify', id=submission.id),
                from_=app.config['WEIRDNESS_NUMBER'],
                to=submission.phone_number,
            )

    return Response(status=200)


@volunteers.route('/submit/verify/<int:id>', methods=('GET', 'POST'))
@protected
def verify(id):
    submission = Submission.query.filter_by(id=id).first_or_404()

    if request.values.get('AnsweredBy') == 'machine_start':
        return render_xml('hang_up.xml')

    gather_times = get_gather_times()

    confirmed = request.values.get('Digits') == '1'
    if confirmed:
        if not submission.create_volunteer():
            return Response(status=409)  # Conflict

    return render_xml(
        'verify.xml',
        action_url=protected_external_url(
            'volunteers.verify', id=submission.id, gather=gather_times),
        phoned=bool(request.args.get('phoned')),
        confirmed=confirmed,
        gather_times=gather_times,
        song_url=external_url('static', filename='troll.mp3', _external=True),
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
