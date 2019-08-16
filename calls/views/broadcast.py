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
            # Cheat code * emulates a weirdness phone outgoing (calls a participant)
            return outgoing_weirdness()
        elif to_number == '#{}'.format(UserCodeConfig.BROADCAST_TO_WEIRDNESS_CODE):
            # Cheat code ## calls the weirdness phone incoming (calls outdoor phone)
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

                message = ('{} is now {}. '.format(
                    code.description, 'disabled' if value else 'enabled') * 2).strip()
                return render_xml('hang_up.xml', message=message, pause=1)

            else:
                return render_xml('hang_up.xml', message='Invalid code. Please try again.')

        else:
            to_number = sanitize_phone_number(to_number)
            if to_number:
                return render_xml(
                    'call.xml',
                    record=True,
                    to_number=to_number,
                    from_number=app.config['BROADCAST_NUMBER'],
                )

    # Catch-all
    return render_xml('hang_up.xml', message=(
        'Your call cannot be completed as dialed. Please eat some cabbage, bring '
        'in your dry cleaning and try your call again. Good bye.'))


@broadcast.route('/incoming', methods=('POST',))
@protected
def incoming():
    call_status = request.values.get('DialCallStatus')

    if call_status == 'completed':
        return render_xml('hang_up.xml', with_song=True)

    elif (
        call_status in ('busy', 'no-answer', 'failed')
        or not UserCodeConfig.get('broadcast_enable_incoming')
    ):
        if (
            random.randint(1, constants.INCOMING_CALLERS_RANDOM_CHANCE_OF_WEIRDNESS) == 1
            and UserCodeConfig.get('random_broadcast_misses_to_weirdness')
        ):
            return outgoing_weirdness()
        else:
            return render_xml('voicemail.xml')

    else:
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
