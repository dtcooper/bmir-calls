from functools import wraps
import re

from twilio.base.exceptions import TwilioRestException

from flask import (
    current_app as app,
    render_template,
    request,
    Response,
    url_for,
)


def sanitize_phone_number(phone_number):
    try:
        return app.twilio.lookups.phone_numbers(
            phone_number).fetch(country_code='US').phone_number
    except TwilioRestException:  # skip coverage
        return False


def protected(route):
    @wraps(route)
    def protected_route(*args, **kwargs):
        password = request.args.get('password', '')
        if password == app.config['API_PASSWORD'] or app.config['DEBUG']:
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


def parse_sip_address(address, number=False):
    if isinstance(address, str):
        match = re.search(r'^sip:([^@]+)@', address)
        if match:
            address = match.group(1)
            if number:
                address = sanitize_phone_number(address)

            return address

    return False

    return match.group(1) if match else False
