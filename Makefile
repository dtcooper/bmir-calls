all: up

up:
	docker-compose up

build:
	docker-compose build

shell:
	docker-compose run --rm --service-ports app bash

test:
	docker-compose run --rm app pytest
