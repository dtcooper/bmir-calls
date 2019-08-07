from flask import (
    render_template,
    Response,
)


def render_xml(template, *args, **kwargs):
    return Response(render_template(template, *args, **kwargs), content_type='text/xml')
