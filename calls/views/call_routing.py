import random

from flask import (
    Blueprint,
    current_app as app,
    request,
)

from calls.models import Volunteer
from calls.utils import (
    parse_sip_address,
    protected,
    render_xml,
    sanitize_phone_number,
)


call_routing = Blueprint('call_routing', __name__, url_prefix='/routing')


def outgoing_weirdness():
    to_address = parse_sip_address(request.form.get('To'))
    if to_address == '1':
        volunteer = Volunteer.get_random_opted_in()

    phone_number = sanitize_phone_number(to_address)
    if phone_number:
        return '<Response><Dial callerId="{}">{}</Dial></Response>'.format(
            app.config['WEIRDNESS_NUMBER'],
            phone_number,
        )
    else:
        return render_xml(
            'hang_up.xml',
            message=('Your call cannot be completed as dialed. Please {}, and try your '
                     'call again.'.format(random.choice(app.config['RANDOM_MESSAGES']))),
        )


@call_routing.route('/outgoing', methods=('POST',))
@protected
def outgoing():
    from_address = parse_sip_address(request.form.get('From'))

    if from_address == app.config['WEIRDNESS_SIP_USERNAME']:
        return outgoing_weirdness()
    elif from_address == app.config['BROADCAST_SIP_USERNAME']:
        return '<Response><Say>Unimplemented. Goodbye.</Say><Hangup /></Response>'
    else:
        return render_xml('reject.xml')
