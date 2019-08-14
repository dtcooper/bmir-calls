import random

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
    get_gather_times,
    parse_sip_address,
    protected,
    protected_external_url,
    render_xml,
    sanitize_phone_number,
)


routing = Blueprint('routing', __name__, url_prefix='/routing')


@routing.route('/outgoing', methods=('POST',))
@protected
def outgoing():
    from_address = parse_sip_address(request.values.get('From'))
    if from_address == app.config['BROADCAST_SIP_USERNAME']:
        return outgoing_broadcast()
    elif from_address == app.config['WEIRDNESS_SIP_USERNAME']:
        return outgoing_weirdness()
    else:
        return render_xml('hang_up.xml', message='Invalid SIP address.')


@routing.route('/outgoing/weirdness', methods=('POST',))
@protected
def outgoing_weirdness():
    # If our submit action on the dialed call comes back with status completed,
    # that means the dialed party hung up. If this happens in the first 30 secs,
    # we'll dial someone else -- otherwise let's hang up on the caller
    if (
        request.values.get('DialCallStatus') == 'completed'
        and int(request.values.get('DialCallDuration', -1)) >= 30
    ):
        return render_xml(
            'hang_up.xml',
            message=('Congratulations! You have won! You will receive a FREE '
                     'Microsoft Zune in 3 to 5 business days.'),
            music_url=app.config['WEIRDNESS_SIGNUP_MUSIC'])
    else:
        is_broadcast = parse_sip_address(
            request.values.get('From')) == app.config['BROADCAST_SIP_USERNAME']

        # 1 in 30 chance we're calling the BMIR broadcast phone (unless this
        # call came routed from the broadcast desk)
        if not is_broadcast and random.randint(1, 30) == 1:
            return render_xml(
                'call.xml',
                timeout=20,  # Sensible 20 timeout here
                record=True,
                from_number=app.config['WEIRDNESS_NUMBER'],
                action_url=protected_external_url('routing.outgoing_weirdness'),
                to_sip_address='{}@{}'.format(
                    app.config['BROADCAST_SIP_USERNAME'],
                    app.config['TWILIO_SIP_DOMAIN'],
                ))

        # Otherwise it's a new call OR the person we called didn't confirm.
        volunteer = Volunteer.get_random_opted_in()

        if not volunteer:
            return render_xml(
                'hang_up.xml',
                # TODO: better music + quotes
                message='You lose. Thanks for playing! Better luck next time!',
                music_url=app.config['WEIRDNESS_SIGNUP_MUSIC'])
        else:
            return render_xml(
                'call.xml',
                from_number=app.config['WEIRDNESS_NUMBER'],
                to_number=volunteer.phone_number,
                record=True,
                action_url=protected_external_url('routing.outgoing_weirdness'),
                whisper_url=protected_external_url('routing.whisper'))


@routing.route('/outgoing/whisper', methods=('POST',))
@protected
def whisper():
    return render_xml(
        'whisper.xml',
        confirmed=bool(request.values.get('Digits')),
        has_gathered=bool(request.args.get('has_gathered')),
        action_url=protected_external_url(
            'routing.whisper', has_gathered='y'),
    )


def outgoing_broadcast():
    to_number = parse_sip_address(request.values.get('To'))
    if to_number == '#':
        # Cheat code # calls the weirdness phone
        return render_xml(
            'call.xml',
            record=True,
            from_number=app.config['BROADCAST_NUMBER'],
            to_sip_address='{}@{}'.format(
                app.config['WEIRDNESS_SIP_USERNAME'],
                app.config['TWILIO_SIP_DOMAIN'],
            ))
    elif to_number == '*':
        # Cheat code * emulates a weirdness phone outgoing (calls a participant)
        return outgoing_weirdness()
    else:
        to_number = sanitize_phone_number(to_number)
        if to_number:
            return render_xml(
                'call.xml',
                record=True,
                to_number=to_number,
                from_number=app.config['BROADCAST_NUMBER'])
        else:
            return render_xml('hang_up.xml', message=(
                'Your call cannot be completed as dialed. Please eat some cabbage, bring '
                'in your dry cleaning and try your call again. Good bye.'))


@routing.route('/incoming/weirdness', methods=('POST',))
@protected
def incoming_weirdness():
    from_number = sanitize_phone_number(request.values.get('From'))
    if not from_number:
        return render_xml(
            'hang_up.xml',
            message='Call with your caller ID unblocked to get through. Goodbye!')

    enrolled = confirm = False

    volunteer = Volunteer.query.filter_by(phone_number=from_number).first()
    if volunteer:
        enrolled = True

    gather_times = get_gather_times()
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
        action_url=protected_external_url('routing.incoming_weirdness', **url_kwargs),
        confirm=confirm,
        enrolled=enrolled,
        gather_times=gather_times,
        song_url=app.config['WEIRDNESS_SIGNUP_MUSIC'],
    )


@routing.route('/incoming/weirdness/sms', methods=('POST',))
@protected
def incoming_weirdness_sms():
    from_number = sanitize_phone_number(request.values.get('From', ''))
    incoming_message = ' '.join(request.values.get('Body', '').lower().split())

    volunteer = Volunteer.query.filter_by(phone_number=from_number).first()
    if volunteer:
        if any(phrase in incoming_message for phrase in ('go away', 'goaway')):
            db.session.delete(volunteer)
            db.session.commit()

            message = ('You will no longer receive calls from the BMIR Phone Experiment.',
                       'To sign back up, go to https://calls.bmir.org/ or text "SIGN UP".')
        else:
            message = ('Text "GO AWAY" to stop receiving calls from the BMIR '
                       'Phone Experiment.')
    else:
        if from_number:
            if any(phrase in incoming_message for phrase in ('sign up', 'signup')):
                submission = Submission(phone_number=from_number)
                db.session.add(submission)
                db.session.commit()
                submission.create_volunteer()

                message = ('You have signed up for the BMIR Phone Experiment! '
                           'Text "GO AWAY" to stop receiving calls.',
                           'NOTE: you could receive a calls 24 hours a day. To select '
                           'times of day to receive calls, go to https://calls.bmir.org/')
            else:
                message = ('Text "SIGN UP" or go to to https://calls.bmir.org/ '
                           'to sign up for the BMIR Phone Experiment.')
        else:
            message = 'Go to https://calls.bmir.org/ to sign up for BMIR Phone Experiment.'

    return render_xml('sms.xml', message=message)
