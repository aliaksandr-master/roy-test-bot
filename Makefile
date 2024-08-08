SHELL:=bash
NOWSTAMP := $(shell bash -c 'date -u +"%Y%m%dT%H%M%S"')
CWD := $(shell bash -c 'pwd')

.PHONY: dev
dev:
	make format
	make lint

.PHONY: lint
lint:
	poetry run ruff check --respect-gitignore --fix --extend-exclude tests ./
	poetry run ruff format --diff --respect-gitignore
	poetry run mypy .
	poetry run pyright src/

.PHONY: format
format:
	poetry run ruff format --respect-gitignore --preview .



app_tg_public:
	python -m src.app_tg_public.main
