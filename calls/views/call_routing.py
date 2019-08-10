from flask import (
    Blueprint,
    current_app as app,
    request,
    Response,
)

from calls.models import Volunteer
from calls.utils import (
    parse_sip_address,
    protected,
    render_xml,
    sanitize_phone_number,
)


call_routing = Blueprint('call_routing', __name__, url_prefix='/routing')


@call_routing.route('/outgoing', methods=('POST', 'GET'))
@protected
def outgoing():
    from_address = parse_sip_address(request.values.get('From'))
    to_address = parse_sip_address(request.values.get('To'))
    if not from_address or to_address:
        return Response(status=400)

    phone_number = None

    # Broadcast phone dials out
    if from_address == app.config['BROADCAST_SIP_USERNAME']:
        phone_number = sanitize_phone_number(to_address)

    # Weirdness phone calls a random caller (unless we have cheat codes)
    elif from_address == app.config['WEIRDNESS_SIP_USERNAME']:
        # Check code: 66 dials out
        if to_address.startswith('66'):
            phone_number = sanitize_phone_number(to_address[2:])
        else:
            # Otherwise let's get a random volunteer who's opted in!
            volunteer = Volunteer.get_random_opted_in()
            if volunteer:
                phone_number = volunteer.phone_number

    if phone_number:
        return render_xml('call.xml', to_number=phone_number,
                          from_number=app.config['WEIRDNESS_NUMBER'])
    else:
        return render_xml(
            'hang_up.xml',
            message=("Your call cannot be completed as dialed. We're not sorry. "
                     'Bathe in milk, eat prunes, face eastward and try your '
                     "call again. But it still probably won't work."))
