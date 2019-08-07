FROM python:3.6

EXPOSE 5000

ENV FLASK_ENV development
ENV FLASK_APP calls

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir /app
WORKDIR /app

COPY requirements.txt requirements_dev.txt /app/
RUN pip install -r requirements.txt -r requirements_dev.txt

COPY . /app
CMD flask run -h 0.0.0.0
