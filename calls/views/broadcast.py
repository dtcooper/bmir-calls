import random

from flask import (
    Blueprint,
    current_app as app,
    request,
    Response,
)

from calls import constants
from calls.models import UserCodeConfig
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
        if to_number == '*':
            app.logger.info('Routing broadcast phone to volunteer')
            # Cheat code * emulates a weirdness phone outgoing (calls a participant)
            return outgoing_weirdness()
        elif to_number == '#{}'.format(UserCodeConfig.BROADCAST_TO_WEIRDNESS_CODE):
            # Cheat code ## calls the weirdness phone incoming (calls outdoor phone)
            app.logger.info('Routing broadcast phone to weirdness phone')
            return render_xml(
                'call.xml',
                record=True,
                timeout=40,
                from_number=app.config['BROADCAST_NUMBER'],
                to_sip_address='{}@{}'.format(
                    app.config['WEIRDNESS_SIP_USERNAME'],
                    app.config['TWILIO_SIP_DOMAIN'],
                ))
        if to_number.startswith('#'):
            code = UserCodeConfig.get_code_by_number(to_number[1:])
            if code:  # Flip code
                value = UserCodeConfig.get(code.name)
                UserCodeConfig.set(code.name, not value)

                app.logger.info('{} = {}'.format(code.name, not value))
                message = ('{} is now {}. '.format(
                    code.description, 'disabled' if value else 'enabled') * 2).strip()
                return render_xml('hang_up.xml', message=message, pause=1)

            else:
                app.logger.info('Invalid code {}'.format(code))
                return render_xml('hang_up.xml', message='Invalid code. Please try again.')

        else:
            to_number = sanitize_phone_number(to_number)
            if to_number:
                app.logger.info('Broadcast phone dialing {}'.format(to_number))
                return render_xml(
                    'call.xml',
                    record=True,
                    to_number=to_number,
                    from_number=app.config['BROADCAST_NUMBER'],
                )

    # Catch-all
    app.logger.warning("Broadcast phone couldn't complete call: {}".format(
        request.values.get('To')))
    return render_xml('hang_up.xml', message=(
        'Your call cannot be completed as dialed. Please eat some cabbage, bring '
        'in your dry cleaning and try your call again. Good bye.'))


@broadcast.route('/incoming', methods=('POST',))
@protected
def incoming():
    call_status = request.values.get('DialCallStatus')
    calling_enabled = UserCodeConfig.get('broadcast_enable_incoming')

    if call_status == 'completed':
        app.logger.info('Broadcast phone hung up on caller')
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
            app.logger.info('Incoming call missed (calling {}) from broadcast won '
                            'lottery. Calling volunteer.'.format(
                                'enabled' if calling_enabled else 'disabled'))
            return outgoing_weirdness()
        else:
            app.logger.info('Sending incoming call missed (calling {}) from '
                            'broadcast to voicemail (lottery {})'.format(
                                'enabled' if calling_enabled else 'disabled',
                                'enabled' if lottery_enabled else 'disabled'))
            return render_xml('voicemail.xml')

    else:
        app.logger.info('Incoming call ringing broadcast phone')
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


@broadcast.route('/sms', methods=('POST',))
@protected
def sms():
    return Response(status=501)
