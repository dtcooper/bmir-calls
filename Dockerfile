FROM python:3.13-bookworm

ENV POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UVICORN_APP=bmir_calls:app \
    UVICORN_FORWARDED_ALLOW_IPS='*' \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PROXY_HEADERS=1 \
    UVICORN_WORKERS=1

ARG POETRY_VERSION=1.8.4
RUN wget -qO - https://install.python-poetry.org | python -
ENV PATH="/root/.local/bin:${PATH}"

ARG DEBUG=0
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && if [ "$DEBUG" -a "$DEBUG" != '0' ]; then \
        echo "alias ls='ls --color=auto'" >> /root/.bashrc \
        && echo "alias rs=uvicorn" >> /root/.bashrc \
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
            sqlite3 \
    ; fi

COPY pyproject.toml poetry.lock /app/
WORKDIR /app
RUN ln -s /.env /app/.env

RUN poetry install --no-root $([ -z "$DEBUG" -o "$DEBUG" = '0' ] && echo '--without=dev')

COPY /static /app/static
COPY /bmir_calls /app/bmir_calls
