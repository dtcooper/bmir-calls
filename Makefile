COMPOSE:=docker compose
SHELL:=/bin/bash
DEBUG=$(shell source .env; [ "$$DEBUG" -a "$$DEBUG" != 0 ] && echo '1')

.PHONY: up
up: CONTAINERS:=
up: .env
	$(COMPOSE) up --remove-orphans$(shell [ -z "$(DEBUG)" -o "$(DEBUG)" = 0 ] && echo ' -d') $(CONTAINERS) || true

.PHONY: shell
shell:
	$(COMPOSE) run --rm --use-aliases --service-ports app bash || true

.PHONY: shell-nodeps
shell-nodeps:
	$(COMPOSE) run --no-deps --rm --entrypoint /bin/bash backend || true

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
	@$(COMPOSE) run --no-deps --rm --entrypoint /bin/sh app -c "black . ; isort . ; flake8 ." || true

.PHONY: check-env
check-env:
	@for f in .env .env.sample ; do \
		sed 's/^#//' "$$f" | sed 's/^\([A-Z_]*\)=.*/\1/' > "/tmp/diff-$$f" ; \
	done ; \
	colordiff -u /tmp/diff-.env.sample /tmp/diff-.env ; \
	rm /tmp/diff-.env*
