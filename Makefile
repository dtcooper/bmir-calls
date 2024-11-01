COMPOSE:=docker compose

.PHONY: up
up: .env
	$(COMPOSE) pull --ignore-buildable
	$(COMPOSE) up --remove-orphans$(shell [ -z "$(DEBUG)" -o "$(DEBUG)" = 0 ] && echo ' -d') $(CONTAINERS) || true

.PHONY: shell
shell:
	$(COMPOSE) run --rm --service-ports app bash || exit 0

.PHONY: build
build:
	$(COMPOSE) build --pull

.PHONY: down
down:
	$(COMPOSE) down --remove-orphans

.PHONY: nginx-nodeps
nginx-nodeps:
	$(COMPOSE) run --no-deps --rm --service-ports nginx || true

.PHONY: lint
lint:
	$(COMPOSE) run --no-deps --rm app poetry run sh -c "black . ; isort . ; flake8 ." || true
