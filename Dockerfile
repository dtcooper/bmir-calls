FROM python:3.13-bookworm

ENV DJANGO_SETTINGS_MODULE=bmir_calls.settings \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

ARG POETRY_VERSION=1.8.4
RUN wget -qO - https://install.python-poetry.org | python -
ENV PATH="/root/.local/bin:${PATH}"
RUN echo '/app' > "$(python -c 'import site; print(site.getsitepackages()[0])')/app.pth"

ARG DEBUG=0
RUN if [ "$DEBUG" -a "$DEBUG" != '0' ]; then \
        echo "alias ls='ls --color=auto'" >> /root/.bashrc \
        && echo "alias rs='./manage.py runserver'" >> /root/.bashrc \
        && echo "alias sp='./manage.py shell_plus'" >> /root/.bashrc \
        && echo '. /etc/bash_completion' >> /root/.bashrc \
        && apt-get update \
        && apt-get upgrade -y \
        && apt-get install --no-install-recommends -y \
            bash-completion \
            iputils-ping \
            less \
            nano \
            netcat-openbsd \
            postgresql-client \
            watchman \
    ; fi

COPY pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install $([ -z "$DEBUG" -o "$DEBUG" = '0' ] && echo '--without=dev') \
    && if [ "$DEBUG" -a "$DEBUG" != 0 ]; then \
        # Download relevant verion's bash completion (in dev only)
        wget -qO /etc/bash_completion.d/django_bash_completion \
            "https://raw.githubusercontent.com/django/django/$(python -c 'import django; print(".".join(map(str, django.VERSION[:2])))')/extras/django_bash_completion" \
    ; fi

COPY entrypoint.sh manage.py /app/
COPY bmir_calls /app/bmir_calls

ENTRYPOINT [ "/app/entrypoint.sh" ]
CMD []
