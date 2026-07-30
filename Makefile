all: format check

format: prettier black ruff

check: mypy pyright checkblack checkruff checkprettier

prettier:
	uv --project . --no-config run ./node_modules/.bin/prettier --write .
pyright:
	uv --project . --no-config run ./node_modules/.bin/pyright

mypy:
	uv --project . --no-config run mypy .

black:
	uv --project . --no-config run black .

ruff:
	uv --project . --no-config run ruff check . --fix

checkruff:
	uv --project . --no-config run ruff check .

checkprettier:
	uv --project . --no-config run ./node_modules/.bin/prettier --check .

checkblack:
	uv --project . --no-config run black --check .

checkeditorconfig:
	editorconfig-checker

test:
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	uv --project . --no-config run pytest

install-pre-commit-hook:
	@echo "Installing pre-commit hook to git"
	@echo "Uninstall the hook with uv run pre-commit uninstall"
	uv run pre-commit install

pre-commit:
	uv --project . --no-config run pre-commit run --all-files


checkbundle:
	@echo "skipping checkbundle"
