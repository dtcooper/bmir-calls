FROM python:3.6

EXPOSE 5000

# Add psql
ENV PGHOST db
ENV PGUSER postgres
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV FLASK_ENV development
ENV FLASK_APP calls

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir /app
WORKDIR /app

COPY requirements_dev.txt /app/
RUN pip install -r requirements_dev.txt

COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY . /app
CMD flask run -h 0.0.0.0
