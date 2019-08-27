import random

from flask import (
    Blueprint,
    current_app as app,
    redirect,
    request,
)

from calls import constants
from calls.models import (
    db,
    Submission,
    Volunteer,
    UserCodeConfig,
)
from calls.utils import (
    get_gather_times,
    parse_sip_address,
    protected,
    protected_external_url,
    render_xml,
    sanitize_phone_number,
)


weirdness = Blueprint('weirdness', __name__, url_prefix='/weirdness')


@weirdness.route('/outgoing', methods=('POST',))
@protected
def outgoing():
    # We can come from the broadcast outgoing route, where we may want to change behaviour
    is_broadcast = parse_sip_address(
        request.values.get('From')) == app.config['BROADCAST_SIP_USERNAME']

    # If our submit action on the dialed call comes back with status completed,
    # that means the dialed party hung up. If this happens in the first 30 secs,
    # we'll dial someone else -- otherwise let's hang up on the caller
    if (
        request.values.get('DialCallStatus') == 'completed'
        and int(request.values.get('DialCallDuration', -1)) >= 30
    ):
        context = {}
        if not is_broadcast:
            context = {
                'message': ('Congratulations! You have won! You will receive a FREE '
                            'Microsoft Zune in 3 to 5 business days.'),
                'with_song': True,
            }
        app.logger.info('Outgoing weirdness call completed')
        return render_xml('hang_up.xml', **context)
    else:
        # 1 in 30 chance we're calling the BMIR broadcast phone (unless this
        # call came routed from the broadcast desk)
        if (
            not is_broadcast
            # Make sure this wasn't an outside caller who won the lottery
            and not request.values.get('To') == app.config['BROADCAST_NUMBER']
            and random.randint(1, constants.WEIRDNESS_RANDOM_CHANCE_OF_RINGING_BROADCAST) == 1
            and UserCodeConfig.get('random_weirdness_to_broadcast')
        ):
            app.logger.info('Outgoing weirdness call won lottery, dialing broadcast phone')
            return render_xml(
                'call.xml',
                timeout=20,
                record=True,
                from_number=app.config['WEIRDNESS_NUMBER'],
                action_url=protected_external_url('weirdness.outgoing'),
                to_sip_address='{}@{}'.format(
                    app.config['BROADCAST_SIP_USERNAME'],
                    app.config['TWILIO_SIP_DOMAIN'],
                ))

        # Otherwise it's a new call OR the person we called didn't confirm.
        multiring = UserCodeConfig.get('weirdness_multiring')
        volunteers = Volunteer.get_random_opted_in(multiring=multiring)

        if volunteers:
            to_numbers = [volunteer.phone_number for volunteer in volunteers]
            app.logger.info('Outgoing weirdness call to {}'.format(
                to_numbers[0] if len(to_numbers) == 1 else to_numbers
            ))
            return render_xml(
                'call.xml',
                record=True,
                timeout=20,
                from_number=app.config['WEIRDNESS_NUMBER'],
                to_numbers=to_numbers,
                action_url=protected_external_url('weirdness.outgoing'),
                whisper_url=protected_external_url('weirdness.whisper'),
            )
        else:
            app.logger.info('Outgoing weirdness call found no volunteers. Hanging up.')
            return render_xml(
                'hang_up.xml',
                message='You lose. Thanks for playing! Better luck next time!',
                with_song=True,
            )


@weirdness.route('/whisper', methods=('POST',))
@protected
def whisper():
    confirmed = bool(request.values.get('Digits'))
    has_gathered = bool(request.args.get('has_gathered'))
    app.logger.info('Whispering to {} (confirmed = {}, gathered = {})'.format(
        request.values.get('To'), confirmed, has_gathered))
    return render_xml(
        'whisper.xml',
        confirmed=confirmed,
        has_gathered=has_gathered,
        action_url=protected_external_url(
            'weirdness.whisper', has_gathered='y'),
    )


@weirdness.route('/incoming', methods=('POST',))
@protected
def incoming():
    from_number = sanitize_phone_number(request.values.get('From'))
    if not from_number:
        app.logger.info('Incoming weirdness with caller ID blocked')
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

                app.logger.info('Volunteer {} removed by call'.format(from_number))
                return render_xml(
                    'hang_up.xml', with_song=True,
                    message=('You will no longer receive calls. To sign back up, '
                             'call this number or go to calls dot B M I R dot org.'))
            else:
                confirm = True
                url_kwargs['confirm'] = 'y'
                del url_kwargs['gather']
        else:
            submission = Submission(phone_number=from_number)
            db.session.add(submission)
            db.session.commit()
            app.logger.info('Volunteer {} added by call'.format(from_number))
            return redirect(protected_external_url(
                'volunteers.verify', id=submission.id, phoned='y'))

    app.logger.info('Got incoming weirdness call from {} (enrolled = {})'.format(
        from_number, enrolled))
    return render_xml(
        'incoming_weirdness.xml',
        action_url=protected_external_url('weirdness.incoming', **url_kwargs),
        confirm=confirm,
        enrolled=enrolled,
        gather_times=gather_times,
    )


@weirdness.route('/sms', methods=('POST',))
@protected
def sms():
    from_number = sanitize_phone_number(request.values.get('From'))
    incoming_message = ' '.join(request.values.get('Body', '').lower().split())

    volunteer = Volunteer.query.filter_by(phone_number=from_number).first()
    if volunteer:
        if any(phrase in incoming_message for phrase in ('go away', 'goaway')):
            db.session.delete(volunteer)
            db.session.commit()
            app.logger.info('Volunteer {} removed by sms'.format(from_number))

            message = ('You will no longer receive calls from the BMIR Phone Experiment.',
                       'To sign back up, go to https://calls.bmir.org/ or text "SIGN UP".')
        else:
            app.logger.info('Got sms from {}'.format(from_number))
            message = ('Text "GO AWAY" to stop receiving calls from the BMIR '
                       'Phone Experiment.')
    else:
        if from_number:
            if any(phrase in incoming_message for phrase in ('sign up', 'signup')):
                submission = Submission(phone_number=from_number)
                db.session.add(submission)
                db.session.commit()
                submission.create_volunteer()

                app.logger.info('Volunteer {} added by sms'.format(from_number))

                message = ('You have signed up for the BMIR Phone Experiment! '
                           'Text "GO AWAY" to stop receiving calls.',
                           'NOTE: you could get a called 24 hours a day. To select '
                           'times of day to receive calls, go to https://calls.bmir.org/')
            else:
                app.logger.info('Got sms from {}'.format(from_number))
                message = ('Text "SIGN UP" or go to to https://calls.bmir.org/ '
                           'to sign up for the BMIR Phone Experiment.')
        else:
            message = 'Go to https://calls.bmir.org/ to sign up for BMIR Phone Experiment.'

    return render_xml('sms.xml', message=message)
