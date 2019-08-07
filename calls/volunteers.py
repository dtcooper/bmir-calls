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
from .utils import render_xml


volunteers = Blueprint('volunteers', __name__, url_prefix='/volunteers')


@volunteers.route('/submit', methods=('POST',))
def submit():
    submission = Submission.from_json(request.get_json())
    db.session.add(submission)
    db.session.commit()

    if submission.valid_phone:
        if submission.enabled:
            app.twilio.calls.create(
                url=url_for('volunteers.verify', _external=True, id=submission.id),
                from_=app.config['WEIRDNESS_NUMBER'],
                to=submission.phone_number,
            )

    return Response(status=200)


@volunteers.route('/submit/verify/<int:id>', methods=('POST',))
def verify(id):
    submission = Submission.query.filter_by(id=id).first_or_404()
    return render_xml('volunteers/verify.xml', submission=submission)
