from flask import (
    current_app as app,
    render_template,
    Response,
    url_for,
)


def render_xml(template, *args, **kwargs):
    return Response(render_template(template, *args, **kwargs), content_type='text/xml')


def protected_url_for(endpoint, *args, **kwargs):
    defaults = {'_external': True, 'password': app.config['API_PASSWORD']}
    defaults.update(kwargs)
    return url_for(endpoint, *args, **defaults)
