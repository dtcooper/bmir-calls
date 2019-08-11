from flask import (
    Blueprint,
    current_app as app,
    redirect,
    request,
)

from calls.models import (
    db,
    Submission,
    Volunteer,
)
from calls.utils import (
    parse_sip_address,
    protected,
    protected_external_url,
    render_xml,
    sanitize_phone_number,
)


call_routing = Blueprint('call_routing', __name__, url_prefix='/routing')


@call_routing.route('/outgoing', methods=('POST',))
@protected
def outgoing():
    from_address = parse_sip_address(request.values.get('From'))
    to_address = parse_sip_address(request.values.get('To'))

    from_number = app.config['WEIRDNESS_NUMBER']
    to_number = None

    # Broadcast phone dials out
    if from_address == app.config['BROADCAST_SIP_USERNAME']:
        from_number = app.config['BROADCAST_NUMBER']
        to_number = sanitize_phone_number(to_address)

    # Weirdness phone calls a random caller (unless we have cheat codes)
    elif from_address == app.config['WEIRDNESS_SIP_USERNAME']:
        # Check code: 66 dials out
        if to_address.startswith('66'):
            to_number = sanitize_phone_number(to_address[2:])
        else:
            # Otherwise let's get a random volunteer who's opted in!
            volunteer = Volunteer.get_random_opted_in()
            if volunteer:
                to_number = volunteer.phone_number

    if to_number:
        return render_xml('call.xml', from_number=from_number, to_number=to_number)
    else:
        return render_xml(
            'hang_up.xml',
            message=("Your call cannot be completed as dialed. We're not sorry. "
                     'Bathe in milk, eat prunes, face eastward and try your '
                     "call again. But it still probably won't work."))


@call_routing.route('/incoming/weirdness', methods=('POST',))
@protected
def incoming_weirdness():
    # TODO: if from_number is none, then say a message saying you must provide
    # a caller ID
    from_number = sanitize_phone_number(request.values.get('From', ''))
    enrolled = confirm = False

    volunteer = Volunteer.query.filter_by(phone_number=from_number).first()
    if volunteer:
        enrolled = True

    try:
        gather_times = int(request.args.get('gather', '0'), 10) + 1
    except ValueError:
        gather_times = 1
    url_kwargs = {'gather': gather_times}

    if request.values.get('Digits') == '1':
        if volunteer:
            if request.args.get('confirm'):
                db.session.delete(volunteer)
                db.session.commit()

                return render_xml(
                    'hang_up.xml',
                    message=('You will no longer receive calls. To sign back up, '
                             'call this number or go to calls dot B M I R dot org.'))
            else:
                confirm = True
                url_kwargs['confirm'] = 'y'
                del url_kwargs['gather_times']
        else:
            submission = Submission(phone_number=from_number)
            db.session.add(submission)
            db.session.commit()
            return redirect(protected_external_url(
                'volunteers.verify', id=submission.id, phoned='y'))

    return render_xml(
        'incoming_weirdness.xml',
        action_url=protected_external_url('call_routing.incoming_weirdness', **url_kwargs),
        confirm=confirm,
        enrolled=enrolled,
        gather_times=gather_times,
        song_url=app.config['WEIRDNESS_SIGNUP_MUSIC'],
    )


@call_routing.route('/incoming/weirdness/sms', methods=('POST',))
@protected
def incoming_weirdness_sms():
    from_number = sanitize_phone_number(request.values.get('From', ''))
    body_lower = ' '.join(request.values.get('Body', '').lower().split())

    volunteer = Volunteer.query.filter_by(phone_number=from_number).first()
    if volunteer:
        if 'no more' in body_lower:
            db.session.delete(volunteer)
            db.session.commit()
            message = ('You will no longer receive calls from the BMIR Phone '
                       'Experiment. To sign back up, go to https://calls.bmir.org/ '
                       'or text "SIGN UP".')
        else:
            message = ('Text "NO MORE" to stop receiving calls from the BMIR '
                       'Phone Experiment.')
    else:
        if from_number:
            if 'sign up' in body_lower:
                submission = Submission(phone_number=from_number)
                db.session.add(submission)
                db.session.commit()
                submission.create_volunteer()
                message = ('You have signed up for the BMIR Phone Experiment. '
                           'Text "NO MORE" to stop receiving calls.')
            else:
                message = ('Call this number, text "SIGN UP" or go to to '
                           'https://calls.bmir.org/ to sign up for the BMIR Phone Experiment.')
        else:
            message = 'Go to https://calls.bmir.org/ to sign up for BMIR Phone Experiment.'

    return render_xml('sms.xml', message=message)
