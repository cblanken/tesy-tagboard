export COMPOSE_FILE := "docker-compose.local.yml"
export COMPOSE_PROFILES := "all"

## Just does not yet manage signals for subprocesses reliably, which can lead to unexpected behavior.
## Exercise caution before expanding its usage in production environments.
## For more information, see https://github.com/casey/just/issues/2473 .


# Default command to list all available commands.
default:
    @just --list

# build: Build python image.
build:
    @echo "Building python image..."
    @docker compose build

# up: Start up containers.
up:
    @echo "Starting up containers..."
    @docker compose up -d --remove-orphans

up-debug:
    @echo "Starting up containers with debug console for Django app..."
    @docker compose --profile debug up -d --remove-orphans
    @docker compose run --rm --service-ports django # to handle python breakpoints
    # Note when exiting (Ctrl-C) the debugger, the other docker services
    # will remain up until brought down with `just down`

up-docs:
    @echo "Starting up docs container..."
    COMPOSE_FILE=docker-compose.docs.yml docker compose up -d

# down: Stop containers.
down:
    @echo "Stopping containers..."
    @docker compose down

down-docs:
    @echo "Stopping docs container..."
    COMPOSE_FILE=docker-compose.docs.yml docker compose down

# prune: Remove containers and their volumes.
docker-prune-volumes *args:
    @echo "Killing containers and removing volumes..."
    @docker compose down -v {{args}}

# logs: View container logs
docker-logs *args:
    @docker compose logs -f {{args}}

# test: run pytest(s)
docker-test *args:
    @docker compose -f docker-compose.local.yml run --rm django pytest {{args}}

# coverage: run pytest(s) with coverage report
docker-coverage *args:
    @docker compose -f docker-compose.local.yml run --rm django coverage run -m pytest
    @docker compose -f docker-compose.local.yml run --rm django coverage report {{args}}

# db backup: creates db backup in /backups dir of postgres container
docker-db-backup *args:
    @docker compose -f docker-compose.local.yml exec postgres backup

# db clean backups: remove all postgres backups in /backups
docker-db-rm-backups *args:
    @docker compose -f docker-compose.local.yml exec -t postgres sh -c 'rm -f /backups/*'

alias m := manage
manage *args:
    DJANGO_READ_DOT_ENV_FILE=True uv run python manage.py {{args}}

alias r := run
run:
    @echo "Starting Tesy's Tagboard..."
    DJANGO_READ_DOT_ENV_FILE=True uv run python manage.py tailwind dev

alias ra := run-async
run-async *args:
    @echo "Starting Tesy's Tagboard in async mode..."
    DJANGO_READ_DOT_ENV_FILE=True uv run uvicorn config.asgi:application --host 0.0.0.0 --port 55555 --reload-include "*.html" {{ args }}

startapp +args:
    @echo "Creating new Django app..."
    uv run python manage.py startapp {{args}}

alias t := test
test *args:
    @echo "Running tests..."
    DJANGO_READ_DOT_ENV_FILE=True pytest

db-reset *args:
    just manage reset_db
    just manage migrate
    just manage createsuperuser --username admin --email tesy-tagboard@example.com

alias mkc := make-component
make-component name:
    #!/usr/bin/env bash
    set -euxo pipefail
    pascal=$(echo '{{name}}' | sed -r 's/(^|_)([a-z])/\U\2/g')
    class_name="${pascal}Component"
    echo "Making '{{name}}' component"
    dir="./tesys_tagboard/components/{{name}}"
    mkdir "$dir"
    py_file="$dir/{{name}}.py"
    touch "$py_file"
    touch "$dir/__init__.py"
    touch "$dir/{{name}}.html"
    touch "$dir/{{name}}.js"
    echo 'from django_components import Component' >> "$py_file"
    echo 'from django_components import register' >> "$py_file"
    echo '' >> "$py_file"
    echo '' >> "$py_file"
    echo '@register("{{name}}")' >> "$py_file"
    echo "class ${class_name}(Component):" >> "$py_file"
    echo '    template_file = "{{name}}.html"' >> "$py_file"
    echo '    js_file = "{{name}}.js"' >> "$py_file"

load-demo:
    @echo "Loading demo data..."
    DJANGO_READ_DOT_ENV_FILE=True uv run python manage.py loaddata demo.json
    cp -r tesys_tagboard/fixtures/uploads/ tesys_tagboard/media/
