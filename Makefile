all: up

up:
	docker-compose up

build:
	docker-compose build

shell:
	docker-compose run --rm --service-ports app bash

dbshell:
	docker-compose run --rm db psql -h db -U postgres

test:
	docker-compose run --rm app pytest
