Development
===========

Getting your development environment setup for Tesy’s Tagboard should be
pretty painless.

First off, the initial structure for the app was based on
`cookiecutter-django <https://cookiecutter-django.readthedocs.io/>`__,
so much of the structure of the application still follows that template.
Of course, refer to the documentation here first, but the
cookiecutter-django docs may also be helpful.

System Requirements
-------------------

This project uses Docker to setup a consistent development environment.
So, all system dependencies are handled by Docker with the exception of
the command runner `just <#just>`__, and `pre-commit <#pre-commit>`__.
Just is a command runner for typical tasks like bringing up and down the
docker dev environment, running tests, and loading demo data etc.
Pre-commit ensures various code linting and formatting is applied.

Read on to install each of these.

Docker
~~~~~~

Please refer to the official `Docker installation
instructions <https://docs.docker.com/engine/install/>`__ to install
Docker on your own system. If you are running a Windows system, the
preferred method is to install `Docker
Desktop <https://docs.docker.com/desktop/>`__.

The `docker-compose <https://docs.docker.com/compose/>`__ plugin is used
to launch all the necessary services for the app, so be sure to install
it as well if it isn’t already.

Just
~~~~

This project uses a command runner called ``just``. It’s not *necessary*
to use ``just`` to proceed with development, but it’s highly
recommended. Otherwise you will need to reference the ``justfile`` to
find the appropriate commands for launching the application and
performing other application management tasks. See the `installation
instructions <https://just.systems/man/en/>`__ for details on how to
install ``just`` on your system.

Launching the App
-----------------

After you’ve installed the `required
dependencies <#system-requirements>`__, then launching the application
is as simple as running the command ``just up``. It may take some time
to build the dev container from scratch for the first time. Expect from
5 to 10 minutes, so maybe go grab a coffee or come back here and keep
reading :)

Environment Configuration
-------------------------

The default development environment env files are located at
``.envs/.local/``

The default environment files all exist under the `.envs <https://github.com/
cblanken/tesys-tagboard/tree/main/.envs>`__
directory, but these should not be modified except with the intention of
changing the default configurations for all users, as these files are
tracked by Git. To provide or override environment variables for your
own instance create a ``.env`` in the project root directory and define
all your custom environment variables there.

For a detailed description of all the environment variables, please see
the :doc:`../configuration/settings`.

Debugging
---------

Besides the usual browser `dev
tools <https://developer.chrome.com/docs/devtools>`__, the dev
environment also includes the `Django Debug
Toolbar <https://django-debug-toolbar.readthedocs.io/en/latest/index.html>`__
. The Debug Toolbar can be enabled by setting the
:envvar:`DJANGO_DEBUG_TOOLBAR` environment variable to ``True`` in your
``.env`` file.

Additionally, you may find it useful to set breakpoints in the django
application to troubleshoot errors. To do so, simply write
``import ipdb; ipdb.set_trace()``. This will set a breakpoint to launch
the IPython debugger wherever that line is executed. Be sure you have
launched the application with ``just up-debug`` so that debugging is
enabled and you have access to the shell when a breakpoint is reached to
perform any debugging. Without running ``just up-debug`` you won't have
access to ipdb to do any debugging.

Pre-commit
----------

The linting and code formatting for this project are handled by
``pre-commit``. Please see the `official installation
instructions <https://pre-commit.com/#installation>`__ to install it for
your system. All of the configured pre-commit hooks may be found in the
`.pre-commit.config-yml </.pre-commit-config-yml>`__ config file.

Once you’ve installed ``pre-commit``, you may then install the git hook
scripts by running ``pre-commit install`` from the project’s root
directory. This will ensure all the required pre-commit hooks will run
every time you make a commit. If you’d like to catch any pre-commit
errors before actually attempting a ``git commit`` or prefer not to
install git hooks, you may run the pre-commit hooks manually with
``pre-commit run``.

Running Tests
-------------

Tests should be run with ``just test``. This will launch pytest in the
dev container with a default number of workers. If you have many cores
on your machine, you may wish to increase the worker count with the
``-n`` flag. For example, running ``just test -n 8`` which may decrease
the test runtime though you will need to experiment with the number for
the best results on your own machine.

All tests should pass or be updated if required before a PR is merged. I
recommend running the tests before each commit (when reasonable) and
certainly before pushing to your feature branch.

Testing Email
-------------

The dev docker environment also includes an instance of
`Mailpit <https://mailpit.axllent.org>`_ which is an email testing
tool. The web interface for mailpit should be reachable at
``http://localhost:8025``. By default, all emails sent by the app will
be sent to mailpit over SMTP and can be viewed for correctness in the
web interface. To manually send emails via the Django app please see the
`official
documentation <https://docs.djangoproject.com/en/6.0/topics/email/#module-django.core.mail>`_.

Testing Third-party Login
-------------------------

Third-party account registration and login requires
some additional setup to test properly.

Discord Auth
~~~~~~~~~~~~

See the official Discord
`documentation <https://docs.discord.com/developers/topics/oauth2>`__ on
how to setup OAuth2.

The relevant environment variables are:

- :envvar:`DJANGO_DISCORD_CLIENT_ID`
- :envvar:`DJANGO_DISCORD_CLIENT_SECRET`
- :envvar:`DJANGO_DISCORD_PUBLIC_KEY`

Testing Production Settings
---------------------------

By default the application will load the ``config.settings.local``
settings module. To override this behavior, you can manage the
application using the productions settings module with the
:envvar:`DJANGO_SETTINGS_MODULE` environment variable like so:

.. code:: sh

   DJANGO_SETTINGS_MODULE=config.settings.production uv run python manage.py`

This will run the Django management command while loading the production
settings allowing for easier iteration than rebuilding the docker image.

Local Development Without Docker
--------------------------------

It *is* possible to develop the application without Docker;
however, it's not recommended or supported. You will have to resolve any
issues you encounter on your own. Regardless, here is a brief breakdown of
what you need to run the application locally without Docker.

UV (Python)
~~~~~~~~~~~

TODO

Database (Postgres)
~~~~~~~~~~~~~~~~~~~

TODO
