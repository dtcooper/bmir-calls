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


def sanitize_phone_number(phone_number, with_country_code=False):
    sanitized = (None, None) if with_country_code else None

    if isinstance(phone_number, str):
        # Replace double zero with plus, because I'm used to that shit!
        for intl_prefix in ('00', '011'):
            if phone_number.startswith(intl_prefix):
                phone_number = '+' + phone_number[len(intl_prefix):]

        try:
            lookup = app.twilio.lookups.phone_numbers(
                phone_number).fetch(country_code='US')
        except TwilioRestException:  # skip coverage
            app.logger.warn('Invalid phone number: {}'.format(phone_number))
            pass
        else:
            if with_country_code:
                sanitized = (lookup.phone_number, lookup.country_code)
            else:
                sanitized = lookup.phone_number

    return sanitized


def protected(route):
    @wraps(route)
    def protected_route(*args, **kwargs):
        password_get = request.args.get('password', '')
        password_auth = request.authorization.password if request.authorization else ''
        if (
            password_get == app.config['API_PASSWORD']
            or password_auth == app.config['API_PASSWORD']
            or app.debug
        ):
            return route(*args, **kwargs)
        else:
            return Response(
                status=401,
                headers={'WWW-Authenticate': 'Basic realm="Password Required"'})
    return protected_route


def render_xml(template, *args, **kwargs):
    return Response(render_template(template, *args, **kwargs), content_type='text/xml')


def protected_external_url(endpoint, *args, **kwargs):
    kwargs.update({
        'password': app.config['API_PASSWORD'],
        '_external': True,
    })
    return url_for(endpoint, *args, **kwargs)


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
