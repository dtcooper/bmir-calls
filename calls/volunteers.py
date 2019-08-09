from flask import (
    Blueprint,
    current_app as app,
    request,
    Response,
)

from .models import (
    Submission,
    Volunteer,
)
from .utils import (
    render_xml,
    protected_url_for,
)


volunteers = Blueprint('volunteers', __name__, url_prefix='/volunteers')


@volunteers.route('/submit', methods=('POST',))
def submit():
    submission = Submission.create_from_json(request.get_json())

    if submission.valid_phone:
        if submission.enabled:
            app.twilio.calls.create(
                url=protected_url_for('volunteers.verify', _external=True, id=submission.id),
                from_=app.config['WEIRDNESS_NUMBER'],
                to=submission.phone_number,
            )

    return Response(status=200)


@volunteers.route('/submit/verify/<int:id>', methods=('POST',))
def verify(id):
    submission = Submission.query.filter_by(id=id).first_or_404()
    return render_xml('volunteers/verify.xml', submission=submission)


@volunteers.route('/')
def json():
    return {
        'submissions': [s.serialize() for s in Submission.query.order_by(
            Submission.id.desc()).all()],
        'volunteers': [v.serialize() for v in Volunteer.query.order_by(
            Volunteer.id.desc()).all()],
        'timezone': str(app.config['SERVER_TZ'].zone),
    }
