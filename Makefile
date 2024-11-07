COMPOSE:=docker compose

.PHONY: up
up: .env
	$(COMPOSE) pull --ignore-buildable
	$(COMPOSE) up --remove-orphans$(shell [ -z "$(DEBUG)" -o "$(DEBUG)" = 0 ] && echo ' -d') $(CONTAINERS) || true

.PHONY: shell
shell:
	$(COMPOSE) run --rm --use-aliases --service-ports app bash || exit 0

.PHONY: build
build:
	$(COMPOSE) build --pull

.PHONY: down
down:
	$(COMPOSE) down --remove-orphans

.PHONY: nginx-background
nginx-background:
	$(COMPOSE) up --no-deps --detach nginx

.PHONY: lint
lint:
	$(COMPOSE) run --no-deps --rm app sh -c "black . ; isort . ; flake8 ." || true
