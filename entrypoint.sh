#!/bin/sh

set -e

if [ ! -f /.env ]; then
    echo 'Missing /.env file! Exiting.'
    exit 1
fi

. /.env

if [ -z "$SECRET_KEY" ]; then
    echo "No SECRET_KEY set. Exiting."
    exit 1
fi

if [ "$DEBUG" = '0' ]; then
    DEBUG=
fi

cd "$(dirname "$0")"

wait-for-it --timeout 0 --service db:5432

./manage.py migrate

if [ "$DEBUG" ]; then
    if [ "$(./manage.py shell -c 'from django.contrib.auth.models import User; print("" if User.objects.exists() else "1")')" = 1 ]; then
        DJANGO_SUPERUSER_PASSWORD=calls ./manage.py createsuperuser --noinput --username calls --email ''
    fi

    export PGHOST=db
    export PGUSER=postgres
    export PGPASSWORD=postgres
fi

if [ "$#" = 0 ]; then
    if [ -z "$DEBUG" ]; then
        # Do this in the background
        ./manage.py collectstatic --noinput &
    fi

    if [ "$DEBUG" ]; then
        exec ./manage.py runserver
    else
        if [ -z "$NUM_GUNICORN_WORKERS" ]; then
            # num_cpus * 2 + 1 workers
            NUM_GUNICORN_WORKERS="$(python -c 'import multiprocessing as m; print(m.cpu_count() * 2 + 1)')"
        fi

        exec gunicorn \
            $GUNICORN_ARGS \
            --access-logfile - \
            --capture-output \
            --forwarded-allow-ips '*' \
            --reuse-port \
            --bind 0.0.0.0:8000 \
            --workers $NUM_GUNICORN_WORKERS \
        bmir_calls.wsgi
    fi
else
    echo "Executing: $*"
    exec "$@"
fi
