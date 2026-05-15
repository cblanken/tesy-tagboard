set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
export COMPOSE_FILE := env("COMPOSE_FILE", "docker-compose.local.yml")
export COMPOSE_PROFILES := "all"

## Just does not yet manage signals for subprocesses reliably, which can lead to unexpected behavior.
## Exercise caution before expanding its usage in production environments.
## For more information, see https://github.com/casey/just/issues/2473 .


# Default command to list all available commands
default:
    @just --list

# Setup default environment
setup-env:
    #!/usr/bin/env bash
    set -euo pipefail
    cp --update=none .envs/.local/.django.example .envs/.local/.django
    cp --update=none .envs/.local/.postgres.example .envs/.local/.postgres

# Build container images
build *args: setup-env
    @echo "Building container images..."
    @docker compose build {{args}}

# Start up containers
up *args: setup-env
    @echo "Starting up containers..."
    @docker compose up -d --remove-orphans {{args}}

# Start up containers and attach python debugger
up-debug: setup-env
    @echo "Starting up containers with debug console for Django app..."
    @docker compose --profile debug up -d --remove-orphans
    @docker compose run --rm --service-ports django # to handle python breakpoints
    # Note when exiting (Ctrl-C) the debugger, the other docker services
    # will remain up until brought down with `just down`

alias whats-up-doc := up-docs
# Start up docs container 🐇
up-docs *args:
    @echo "Starting up docs container..."
    COMPOSE_FILE=docker-compose.docs.yml docker compose up -d {{args}}

# Stop containers
down *args:
    @echo "Stopping containers..."
    @docker compose down {{args}}

# Stop docker "debug" profile containers
down-debug:
    @echo "Stopping containers required for Django app debug..."
    @docker compose --profile debug down

# Stop docs container
down-docs:
    @echo "Stopping docs container..."
    COMPOSE_FILE=docker-compose.docs.yml docker compose down

# Remove containers and their volumes
prune-volumes *args:
    @echo "Killing containers and removing volumes..."
    @docker compose down -v {{args}}

# View container logs
logs *args:
    @docker compose logs -f {{args}}

alias t := test
# Run pytest(s)
test *args:
    @docker compose run --rm django pytest -n 4 {{args}}

# Run pytest(s) with coverage report
coverage *args:
    @docker compose run --rm django coverage run -m pytest
    @docker compose run --rm django coverage report {{args}}


alias tc := type-checking
# Pre-commit linting and formatting
type-checking *args:
    @docker compose run --rm django mypy {{args}}

alias sh := shell
# Get an interactive shell to the Django app
shell *args:
    @docker compose exec {{args}} django /bin/bash

# Creates db backup in the /backups dir of postgres container
db-backup:
    @docker compose exec postgres backup

# Remove all postgres backups in /backups
db-rm-backups:
    @docker compose exec -t postgres sh -c 'rm -f /backups/*'

alias m := manage
# Django management CLI
manage *args:
    @docker compose exec -t django python manage.py {{args}}

alias r := run
# Start the Django app on the host system
run:
    @echo "Starting Tesy's Tagboard..."
    uv run python manage.py tailwind dev

alias ra := run-async
# Start the Django app on the host system via uvicorn (asgi)
run-async *args:
    @echo "Starting Tesy's Tagboard in async mode..."
    uv run uvicorn config.asgi:application --host 0.0.0.0 --port 55555 --reload-include "*.html" {{ args }}

# Reset the database and prompt for a new admin password
db-reset superuser_name="admin":
    just manage reset_db && just manage migrate && just manage createsuperuser --username {{superuser_name}} --email tesy-tagboard@example.com

alias mkc := make-component
# Create a new django-component with a given name
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

clean-media:
    @echo "Cleaning out media folder..."
    rm -rf tesys_tagboard/media/*

# Begin a session with the Redis CLI
redis:
    @echo "Connecting to the Redis CLI..."
    @docker compose exec redis redis-cli

# Flush all entries from the caching backend
flush-cache:
    @echo "Flushing all entries of the cache..."
    @just manage clear_cache
