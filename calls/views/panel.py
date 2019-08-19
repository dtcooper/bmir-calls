import json

from flask import (
    Blueprint,
    current_app as app,
    redirect,
    render_template,
    request,
    url_for,
)

from calls import constants
from calls.models import (
    Text,
    UserCodeConfig,
    Voicemail,
)
from calls.utils import protected


panel = Blueprint('panel', __name__, url_prefix='/panel')


@panel.route('/', methods=('GET', 'POST'))
@protected
def landing():
    if request.method == 'POST':
        value = json.loads(request.values.get('ringer'))
        app.logger.info(
            'Updating code "broadcast_enable_incoming" = {} (from UI)'.format(value))
        UserCodeConfig.set('broadcast_enable_incoming', value)
        return redirect(url_for('panel.landing'))

    return render_template(
        'panel.html',
        show_all=bool(request.args.get('all')),
        codes=UserCodeConfig.CODES,
        outside_code=UserCodeConfig.BROADCAST_TO_WEIRDNESS_CODE,
    )


@panel.route('/data')
@protected
def data():
    # Pool all texts and voicemails together, sorted by (created, id) reversed
    items = []
    for cls in (Text, Voicemail):
        type_name = cls.__name__.lower()
        after_id = int(request.args.get('after_{}_id'.format(type_name), -1))

        query = cls.query.order_by(cls.created.desc())

        if after_id > -1:
            query = query.filter(cls.id > after_id)

        if request.args.get('all'):
            query = query.limit(constants.MAX_PANEL_ITEMS)

        for item in query.all():
            data = item.serialize()
            data['type'] = type_name
            items.append((item.created, item.id, data))
    items.sort(key=lambda item: (item[0], item[1]))

    return {
        'items': [item[-1] for item in items],
        'codes': [
            (code.name, UserCodeConfig.get(code.name))
            for code in UserCodeConfig.CODES
        ],
    }
