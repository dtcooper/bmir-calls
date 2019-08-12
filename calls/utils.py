from functools import wraps
import re
from urllib.parse import unquote

from twilio.base.exceptions import TwilioRestException

from flask import (
    current_app as app,
    render_template,
    request,
    Response,
    url_for,
)


def sanitize_phone_number(phone_number):
    # Replace double zero with plus, because I'm used to that shit!
    if phone_number.startswith('00'):
        phone_number = '+' + phone_number[2:]

    try:
        return app.twilio.lookups.phone_numbers(
            phone_number).fetch(country_code='US').phone_number
    except TwilioRestException:  # skip coverage
        app.logger.warn('Invalid phone number: {}'.format(phone_number))
        return None


def protected(route):
    @wraps(route)
    def protected_route(*args, **kwargs):
        password = request.args.get('password', '')
        if password == app.config['API_PASSWORD'] or app.debug:
            return route(*args, **kwargs)
        else:
            return Response(status=403)
    return protected_route


def render_xml(template, *args, **kwargs):
    return Response(render_template(template, *args, **kwargs), content_type='text/xml')


def protected_external_url(endpoint, *args, **kwargs):
    defaults = {'_external': True, 'password': app.config['API_PASSWORD']}
    defaults.update(kwargs)
    return url_for(endpoint, *args, **defaults)


def parse_sip_address(address):
    if isinstance(address, str):
        match = re.search(r'^sip:([^@]+)@', address)
        if match:
            return unquote(match.group(1))

    return None


def get_gather_times():
    try:
        times = int(request.args.get('gather', '0'), 10) + 1
    except ValueError:
        times = 1

    return times
