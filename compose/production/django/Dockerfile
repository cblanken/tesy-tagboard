ARG PYTHON_VERSION="3.14"
ARG NODE_VERSION="24"
ARG APP_HOME="/app"
ARG TAILWIND_THEME_HOME="/app/tesys_tagboard/theme"
ARG TAILWIND_THEME_SRC="/app/tesys_tagboard/theme/static_src"
ARG TAILWIND_THEME_DIST="/app/tesys_tagboard/theme/static"


#===================
# Python build stage
#===================
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS python-build-stage

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
ARG APP_HOME

WORKDIR ${APP_HOME}

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg dependencies
  libpq-dev \
  # libmagic for file detection
  libmagic1 \
  curl

# Requirements are installed here to ensure they will be cached.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY . ${APP_HOME}

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev


#============================
# Tailwind styles build stage
#============================
FROM docker.io/library/node:${NODE_VERSION}-alpine AS tailwind-build-stage
ARG APP_HOME
ARG TAILWIND_THEME_SRC

COPY . ${APP_HOME}
WORKDIR ${TAILWIND_THEME_SRC}
RUN npm install && npm run build

#===================
# Python 'run' stage
#===================
FROM python:${PYTHON_VERSION}-slim-bookworm AS python-run-stage
ARG APP_HOME

WORKDIR ${APP_HOME}

RUN addgroup --system django \
  && adduser --system --ingroup django django


# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
  # psycopg dependencies
  libpq-dev \
  # Translations dependencies
  gettext \
  # libmagic for file detection
  libmagic1 \
  # entrypoint
  wait-for-it \
  # cleaning up unused files
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

COPY --chown=django:django ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint


COPY --chown=django:django ./compose/production/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

# Copy the application from the builder
ARG TAILWIND_THEME_DIST
COPY --from=python-build-stage --chown=django:django ${APP_HOME} ${APP_HOME}
COPY --from=tailwind-build-stage --chown=django:django ${TAILWIND_THEME_DIST} ${TAILWIND_THEME_DIST}

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# make django owner of the WORKDIR directory as well.
RUN chown django:django ${APP_HOME}

USER django

# explicitly create static and media folders
RUN mkdir -p ${APP_HOME}/staticfiles
RUN mkdir -p ${APP_HOME}/tesys_tagboard/media/images
RUN mkdir -p ${APP_HOME}/tesys_tagboard/media/thumbnails
RUN mkdir -p ${APP_HOME}/tesys_tagboard/theme/static


RUN DATABASE_URL="" \
  DJANGO_SETTINGS_MODULE="config.settings.test" \
  python manage.py compilemessages

ENTRYPOINT ["/entrypoint"]
