import datetime
import random

from flask import (
    Blueprint,
    current_app as app,
    request,
    Response,
)

from calls import constants
from calls.models import (
    db,
    Text,
    UserCodeConfig,
    Voicemail,
)
from calls.utils import (
    parse_sip_address,
    protected,
    protected_external_url,
    render_xml,
    sanitize_phone_number,
)
from calls.views.weirdness import outgoing as outgoing_weirdness


broadcast = Blueprint('broadcast', __name__, url_prefix='/broadcast')


# Gets routed by app.outgoing
def outgoing():
    to_number = parse_sip_address(request.values.get('To'))
    if to_number:
        # if to_number == '*':
        #     app.logger.info('Outgoing broadcast call routing to volunteer')
        #     # Cheat code * emulates a weirdness phone outgoing (calls a participant)
        #     return outgoing_weirdness()
        # elif to_number == '#{}'.format(UserCodeConfig.BROADCAST_TO_WEIRDNESS_CODE):
        #     # Cheat code ## calls the weirdness phone incoming (calls outdoor phone)
        #     app.logger.info('Routing broadcast phone to weirdness phone')
        #     return render_xml(
        #         'call.xml',
        #         record=True,
        #         timeout=40,
        #         from_number=app.config['BROADCAST_NUMBER'],
        #         to_sip_address='{}@{}'.format(
        #             app.config['WEIRDNESS_SIP_USERNAME'],
        #             app.config['TWILIO_SIP_DOMAIN'],
        #         ))
        # if to_number.startswith('#'):
        #     code = UserCodeConfig.get_code_by_number(to_number[1:])
        #     if code:  # Flip code
        #         value = UserCodeConfig.get(code.name)
        #         UserCodeConfig.set(code.name, not value)

        #         app.logger.info('Updating code "{}" = {}'.format(code.name, not value))
        #         message = ('{} is now {}. '.format(
        #             code.description, 'disabled' if value else 'enabled') * 2).strip()
        #         return render_xml('hang_up.xml', message=message, pause=1)

        #     else:
        #         app.logger.info('Invalid code {}'.format(to_number))
        #         return render_xml('hang_up.xml', message='Invalid code. Please try again.')

        # else:
        to_number = sanitize_phone_number(to_number)
        if to_number:
            app.logger.info('Outgoing broadcast call dialing: {}'.format(to_number))
            return render_xml(
                'call.xml',
                record=True,
                to_number=to_number,
                from_number=app.config['BROADCAST_NUMBER'],
            )

    # Catch-all
    app.logger.warning("Outgoing broadcast call couldn't complete: {}".format(
        request.values.get('To')))
    return render_xml('hang_up.xml', message=(
        'Your call cannot be completed as dialed. Please eat some cabbage, bring '
        'in your dry cleaning and try your call again. You probably got the number wrong. Good bye.'))


@broadcast.route('/incoming', methods=('POST',))
@protected
def incoming():
    if request.args.get('voicemail'):
        return render_xml(
            'hang_up.xml', with_song=True,
            message='Did you want to re-record that? Too bad.')

    call_status = request.values.get('DialCallStatus')
    calling_enabled = UserCodeConfig.get('broadcast_enable_incoming')

    if call_status == 'completed':
        app.logger.info('Broadcast hung up on incoming caller')
        return render_xml('hang_up.xml', with_song=True)

    elif (
        call_status in ('busy', 'no-answer', 'failed')
        or not calling_enabled
    ):
        lottery_enabled = UserCodeConfig.get('random_broadcast_misses_to_weirdness')
        if (
            random.randint(1, constants.INCOMING_CALLERS_RANDOM_CHANCE_OF_WEIRDNESS) == 1
            and lottery_enabled
        ):
            app.logger.info('Incoming broadcast call missed (calling {}) won '
                            'lottery. Calling volunteer.'.format(
                                'enabled' if calling_enabled else 'disabled'))
            return outgoing_weirdness()
        else:
            app.logger.info('Sending incoming broadcast call missed (calling {}) '
                            'from broadcast to voicemail (lottery {})'.format(
                                'enabled' if calling_enabled else 'disabled',
                                'enabled' if lottery_enabled else 'disabled'))
            return render_xml(
                'voicemail.xml',
                action_url=protected_external_url('broadcast.incoming', voicemail='y'),
                transcribe_callback_url=protected_external_url('broadcast.transcribe')
            )

    else:
        app.logger.info('Incoming broadcast call ringing')
        return render_xml(
            'call.xml',
            record=True,
            action_url=protected_external_url('broadcast.incoming'),
            from_number=app.config['BROADCAST_NUMBER'],
            to_sip_address='{}@{}'.format(
                app.config['BROADCAST_SIP_USERNAME'],
                app.config['TWILIO_SIP_DOMAIN']
            ),
        )


@broadcast.route('/transcribe', methods=('POST',))
@protected
def transcribe():
    from_number = request.values.get('From')
    voicemail = Voicemail(
        phone_number=from_number,
        transcription=request.values.get('TranscriptionText'),
        url=request.values.get('RecordingUrl'),
    )
    db.session.add(voicemail)
    db.session.commit()

    # This could fail, and we wouldn't want to lose the voicemail
    voicemail.duration = datetime.timedelta(
        seconds=int(app.twilio.recordings.get(
            request.values.get('RecordingSid')).fetch().duration))
    db.session.add(voicemail)
    db.session.commit()

    app.logger.info('Got voicemail from {}'.format(from_number))
    return Response(status=204)


@broadcast.route('/sms', methods=('POST',))
@protected
def sms():
    from_number = request.values.get('From')
    text = Text(phone_number=from_number, body=request.values.get('Body'))
    db.session.add(text)
    db.session.commit()

    app.logger.info('Received sms from {}'.format(from_number))
    return Response(status=204)
