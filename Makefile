all: up

up:
	docker-compose up

build:
	docker pull "$$(grep '^FROM' docker/Dockerfile.app | head -n 1 | cut -d ' ' -f 2)"
	docker pull "$$(grep '^FROM' docker/Dockerfile.db | head -n 1 | cut -d ' ' -f 2)"
	docker-compose build

shell:
	docker-compose run --rm --service-ports app bash

dbshell:
	docker-compose run --rm app psql

test:
	docker-compose run --rm app pytest
