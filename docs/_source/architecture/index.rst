Architecture
============

This document provides an overview of the layout of the project and
describes the general architecture for the application and it’s various
services.

.. toctree::
   :maxdepth: 1

   frontend
   backend
   configuration

Tech Stack
-------------
Here is a list of modules, packages, and frameworks used to build Tesy's Tagboard. It's not exhaustive, but points to some important documentation for hacking on the project.

* `Django <https://www.djangoproject.com>`_ as the backbone web framework for the application

  * `django-environ <https://django-environ.readthedocs.io/en/latest/>`_ for handling environment variables using the `Twelve-factor <https://www.12factor.net>`_ methodology
  * `django-allauth <https://docs.allauth.org/en/latest/>`_ for handling authentication flows via username, email, and third-party authentication
  * `django-ninja <https://django-ninja.dev>`_ for buliding and documenting the REST API
  * `whitenoise <https://whitenoise.readthedocs.io/en/latest/>`_ for serving static files

* `pytest <https://docs.pytest.org/en/stable/>`_ for backend testing
* `docker <https://docs.docker.com/engine/>`__ and `docker-compose <https://docs.docker.com/compose/>`__ for development environment setup and production deployment
* `HTMX <https://htmx.org>`_ for frontend interactivity and dynamic content loading
* `Tailwind <https://tailwindcss.com>`_ CSS styling
* `DaisyUI <https://daisyui.com>`_ Component library with semantic class naming on top of Tailwind


Configuration
-------------

TODO

Docker
~~~~~~

The docker-compose files for `dev <https://github.com/cblanken/tesys-tagboard/blob/main/docker-compose.local.yml>`_,
`production <https://github.com/cblanken/tesys-tagboard/blob/main/docker-compose.production.yml>`__, and `the
docs <https://github.com/cblanken/tesys-tagboard/blob/main/docker-compose.docs.yml>`__ are available in the project root directory with the related build files available in `./compose/ <https://github.com/cblanken/tesys-tagboard/blob/main/compose>`__.
