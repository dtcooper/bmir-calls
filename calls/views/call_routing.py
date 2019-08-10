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
)


call_routing = Blueprint('call_routing', __name__, url_prefix='/routing')


def outgoing_weirdness():
    to_address = parse_sip_address(request.form.get('To'), number=True)
    print('Calling {}'.format(to_address))
    return '<Response><Dial callerId="{}">{}</Dial></Response>'.format(
        app.config['WEIRDNESS_NUMBER'],
        to_address,
    )


@call_routing.route('/outgoing', methods=('POST',))
@protected
def outgoing():
    from_address = parse_sip_address(request.form.get('From'))
    print('From: {} [{}]'.format(
        parse_sip_address(request.form.get('From')), request.form.get('From')))
    print('  To: {} [{}]'.format(
        parse_sip_address(request.form.get('To')), request.form.get('To')))
    if from_address == app.config['WEIRDNESS_SIP_USERNAME']:
        return outgoing_weirdness()
    elif from_address == app.config['BROADCAST_SIP_USERNAME']:
        return '<Response><Say>Unimplemented. Goodbye.</Say><Hangup /></Response>'
    else:
        return render_xml('reject.xml')
