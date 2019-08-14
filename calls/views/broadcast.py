from flask import (
    Blueprint,
    current_app as app,
    request,
    Response,
)

from calls.utils import (
    parse_sip_address,
    protected,
    render_xml,
    sanitize_phone_number,
)
from calls.views.weirdness import outgoing as outgoing_weirdness


broadcast = Blueprint('broadcast', __name__, url_prefix='/broadcast')


# Gets routed by app.outgoing
def outgoing():
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


@broadcast.route('/incoming', methods=('POST',))
@protected
def incoming():
    return Response(status=501)  # Unimplemented


@broadcast.route('/sms', methods=('POST',))
@protected
def sms():
    return Response(status=501)
