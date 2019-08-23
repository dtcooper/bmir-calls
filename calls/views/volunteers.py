from twilio.base.exceptions import TwilioRestException

from flask import (
    Blueprint,
    current_app as app,
    request,
    Response,
)

from calls import constants
from calls.models import (
    db,
    Submission,
    Volunteer,
)
from calls.utils import (
    get_gather_times,
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
            app.logger.info('Volunteer {} updated by form'.format(volunteer.phone_number))

            try:
                app.twilio.messages.create(
                    body='Thanks for updating your BMIR Phone Experiment submission.',
                    from_=app.config['WEIRDNESS_NUMBER'],
                    to=submission.phone_number,
                )
            except TwilioRestException:  # skip coverage
                pass

        else:
            app.logger.info('Submission {} created (valid phone)'.format(
                submission.phone_number))
            app.twilio.calls.create(
                machine_detection='Enable',
                machine_detection_silence_timeout=3000,
                url=protected_external_url('volunteers.verify', id=submission.id),
                from_=app.config['WEIRDNESS_NUMBER'],
                to=submission.phone_number,
            )
    else:
        app.logger.info('Submission {} created (invalid phone)'.format(
            submission.phone_number))

    return Response(status=200)


@volunteers.route('/submit/verify/<int:id>', methods=('GET', 'POST'))
@protected
def verify(id):
    submission = Submission.query.filter_by(id=id).first_or_404()

    if request.values.get('AnsweredBy') == 'machine_start':
        app.logger.warning(
            "Couldn't verify submission id={} because of answering machine start".format(
                submission.id))
        return render_xml('hang_up.xml')

    gather_times = get_gather_times()

    confirmed = request.values.get('Digits') == '1'
    if confirmed:
        if submission.create_volunteer():
            app.logger.info('Volunteer {} added by call'.format(submission.phone_number))
        else:
            app.logger.warning(
                "Couldn't create volunteer for submission id={}".format(submission.id))
            return Response(status=409)  # Conflict

    return render_xml(
        'verify.xml',
        action_url=protected_external_url(
            'volunteers.verify', id=submission.id, gather=gather_times),
        phoned=bool(request.args.get('phoned')),
        confirmed=confirmed,
        gather_times=gather_times,
    )


@volunteers.route('/')
@protected
def json():
    return {
        'submissions': [s.serialize() for s in Submission.query.order_by(
            Submission.id.desc()).all()],
        'volunteers': [v.serialize() for v in Volunteer.query.order_by(
            Volunteer.id.desc()).all()],
        'timezone': str(constants.SERVER_TZ.zone),
    }


@volunteers.route('/stats')
@protected
def json_stats():
    unique_submissions = Submission.query.filter_by(
        valid_phone=True).distinct('phone_number').count()
    num_volunteers = Volunteer.query.count()
    unique_unconfirmed = unique_submissions - num_volunteers

    return {
        'total_submissions': Submission.query.count(),
        'unique_submissions': unique_submissions,
        'unique_unconfirmed': unique_unconfirmed,
        'num_volunteers': num_volunteers,
        'conversion': round(
            (num_volunteers / max(num_volunteers + unique_unconfirmed, 1)) * 100, 2),
        'num_volunteers_called': Volunteer.query.filter(
            Volunteer.last_called.isnot(None)).count(),
    }
