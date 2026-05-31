Settings
========

Environment Variable Overview
-----------------------------

Most settings are defined by environment variables. They may be set in
an ``.env`` file in the project’s root directory to adjust various
aspects of the deployment.

See their usage details below.

General App Settings
~~~~~~~~~~~~~~~~~~~~

These environment variables are read by the Django app and thus have a
corresponding value in Django accessible via ``django.conf.settings``.

================================================== ==================================== ====================== =======================
Environment Variable                               Django Setting                       Production Default     Development Default
================================================== ==================================== ====================== =======================
:envvar:`ACCOUNT_EMAIL_VERIFICATION`               ``DJANGO_EMAIL_VERIFICATION``        ``optional``           ``optional``
:envvar:`DATABASE_URL`                             ``DATABASES["default"]``
:envvar:`DJANGOADMIN_FORCE_ALLAUTH`                ``DJANGO_ADMIN_FORCE_ALLAUTH``       ``False``              ``False``
:envvar:`DJANGO_ACCOUNT_ALLOW_REGISTRATION`        ``ACCOUNT_ALLOW_REGISTRATION``       ``True``               ``True``
:envvar:`DJANGO_ADMINS`                            ``ADMINS``                           ``[]``                 ``[]``
:envvar:`DJANGO_ADMIN_URL`                         ``ADMIN_URL``                        ``/admin``
:envvar:`DJANGO_ALLOWED_HOSTS`                     ``ALLOWED_HOSTS``
:envvar:`DJANGO_DEBUG_TOOLBAR`                     ``DEBUG_TOOLBAR``                                           ``True``
:envvar:`DJANGO_DEBUG`                             ``DEBUG``                            ``False``              ``True``
:envvar:`DJANGO_ENABLE_MFA`                        ``ENABLE_MFA``                       ``False``              ``False``
:envvar:`DJANGO_HOMEPAGE_LINKS`                    ``HOMEPAGE_LINKS``
:envvar:`DJANGO_SECRET_KEY`                        ``SECRET_KEY``
:envvar:`DJANGO_SECURE_CONTENT_TYPE_NOSNIFF`       ``SECURE_CONTENT_TYPE_NOSNIFF``                             ``True``
:envvar:`DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`    ``SECURE_HSTS_INCLUDE_SUBDOMAINS``                          ``True``
:envvar:`DJANGO_SECURE_HSTS_PRELOAD`               ``SECURE_HSTS_PRELOAD``                                     ``True``
:envvar:`DJANGO_SECURE_SSL_REDIRECT`               ``SECURE_SSL_REDIRECT``                                     ``True``
:envvar:`DJANGO_SILKY_PYTHON_PROFILER_BINARY`      ``SILKY_PYTHON_PROFILER_BINARY``     ``False``              ``False``
:envvar:`DJANGO_SILKY_PYTHON_PROFILER`             ``SILKY_PYTHON_PROFILER``            ``False``              ``False``
:envvar:`DJANGO_SOCIAL_LOGIN_ENABLED`              ``SOCIALACCOUNT_ENABLED``            ``True``               ``True``
:envvar:`DJANGO_TITLE`                             ``TITLE``                            ``Tesy's Tagboard``    ``Tesy's Tagboard``
:envvar:`USE_DOCKER`                                                                    ``yes``                ``yes``
================================================== ==================================== ====================== =======================

Email Settings
~~~~~~~~~~~~~~

======================================= ========================= =============================================== ================================
Environment Variable                    Django Setting            Production Default                              Development Default
======================================= ========================= =============================================== ================================
:envvar:`DJANGO_DEFAULT_FROM_EMAIL`     ``DEFAULT_FROM_EMAIL``
:envvar:`DJANGO_EMAIL_BACKEND`          ``EMAIL_BACKEND``         ``django.core.mail.backends.smtp.EmailBackend`` ``django.core.mail.backends.smtp.EmailBackend``
:envvar:`DJANGO_EMAIL_HOST_PASSWORD`    ``EMAIL_HOST_PASSWORD``                                                   ``tesys_tagboard_local_mailpit``
:envvar:`DJANGO_EMAIL_HOST_USER`        ``EMAIL_HOST_USER``
:envvar:`DJANGO_EMAIL_HOST`             ``EMAIL_HOST``                                                            ``tesys_tagboard_local_mailpit``
:envvar:`DJANGO_EMAIL_PORT`             ``EMAIL_PORT``                                                            ``1025``
:envvar:`DJANGO_SERVER_EMAIL`           ``SERVER_EMAIL``          ``DJANGO_DEFAULT_FROM_EMAIL``
======================================= ========================= =============================================== ================================


Database Settings
~~~~~~~~~~~~~~~~~

=========================== ==================
Environment Variable        Default
=========================== ==================
:envvar:`POSTGRES_DB`       ``tesys_tagboard``
:envvar:`POSTGRES_PASSWORD`
:envvar:`POSTGRES_PORT`     ``5432``
:envvar:`POSTGRES_USER`
=========================== ==================


Third-party Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~

======================================= ================== ====================== =======================
Environment Variable                    Django Setting     Production Default     Development Default
======================================= ================== ====================== =======================
:envvar:`DJANGO_DISCORD_CLIENT_ID`
:envvar:`DJANGO_DISCORD_CLIENT_SECRET`
:envvar:`DJANGO_DISCORD_PUBLIC_KEY`
======================================= ================== ====================== =======================


Environment Variable Usage
--------------------------
Detailed descriptions of each environment variable and their intended usage.

.. envvar:: ACCOUNT_EMAIL_VERIFICATION

====================== ===========================================================
Options
====================== ===========================================================
``optional`` (default) User's *MAY* optionally provide an email at signup which may be used for password resets and other notifications.
``mandatory``          User's *MUST* provide an email
``none``               User's *CANNOT* provide an email. This option usually corresponds with an alternative third-party authentication option. Otherwise user's won't be able to make accounts at all.
====================== ===========================================================


.. envvar:: DATABASE_URL

By default, the database URL used by the Django application to communicate with the Postgres database
is generated from the `Database Settings`_. This setting will override that generated database URL.

.. envvar:: DJANGOADMIN_FORCE_ALLAUTH

TODO

.. envvar:: DJANGO_ACCOUNT_ALLOW_REGISTRATION

TODO

.. envvar:: DJANGO_ADMINS

TODO

.. envvar:: DJANGO_ADMIN_URL

The URL for the admin dashboard. It is recommended to change this from the default
value to help prevent authenticaton attacks on the admin dashboard.

.. envvar:: DJANGO_ALLOWED_HOSTS

This setting configures the app to accept requests from a list of hosts. When deployed via Docker, this
value should not need to be changed from the default. See the relevant
`Django docs <https://docs.djangoproject.com/en/6.0/ref/settings/#allowed-hosts>`__ for
more details.

.. envvar:: DJANGO_DEBUG_TOOLBAR

This a development only setting which enables the `Django Debug Toolbar <https://django-debug-toolbar.readthedocs.io>`__.
It has no effect on a production deployment.

.. envvar:: DJANGO_DEBUG
..

This setting enables or disables Django's `Debug Mode <https://docs.djangoproject.com/en/6.0/ref/settings/#debug>`__
which will cause the app to display detailed error messages and additional info about the runtime environment.
This setting **SHOULD NOT** be enabled in a production deployment unless you know what you're doing.

.. envvar:: DJANGO_DEFAULT_FROM_EMAIL

TODO

.. envvar:: DJANGO_DISCORD_CLIENT_ID

The client ID for Discord third-party login.

.. envvar:: DJANGO_DISCORD_CLIENT_SECRET

The client secret for Discord third-party login.

.. envvar:: DJANGO_DISCORD_PUBLIC_KEY

The public key for Discord third-party login.

.. envvar:: DJANGO_EMAIL_BACKEND

The email backend used by Django to handle emails. See the Django
`Email backends <https://docs.djangoproject.com/en/6.0/topics/email/#email-backends>`__ documentation
for more details.

========================================================= ===========================================================
Options
========================================================= ===========================================================
``django.core.mail.backends.smtp.EmailBackend`` (default) use the `Django SMTP email backend <https://docs.djangoproject.com/en/6.0/topics/email/#smtp-backend>`__
``anymail.backends.mailgun.EmailBackend``                 use the `Anymail Mailgun email backend <https://anymail.dev/en/stable/esps/mailgun/>`__
``anymail.backends.mailtrap.EmailBackend``                use the `Anymail Mailtrap email backend <https://anymail.dev/en/stable/esps/mailtrap/>`__
========================================================= ===========================================================

.. note:: Setting either :envvar:`MAILGUN_API_KEY` or :envvar:`MAILTRAP_API_TOKEN` will automatically override this setting to use the appropriate email backend.


.. envvar:: DJANGO_EMAIL_HOST_PASSWORD

The password to use for the SMTP server defined in :envvar:`DJANGO_EMAIL_HOST`.

.. envvar:: DJANGO_EMAIL_HOST_USER

The username to use for the SMTP server defined in :envvar:`DJANGO_EMAIL_HOST`.

.. envvar:: DJANGO_EMAIL_HOST

The host used for sending email.

.. envvar:: DJANGO_EMAIL_PORT

The port to use for the SMTP server defined in :envvar:`DJANGO_EMAIL_HOST`.

.. envvar:: DJANGO_ENABLE_MFA

Enables MFA (multifactor authentication).

TODO: describe MFA options

.. envvar:: DJANGO_HOMEPAGE_LINKS

A list describing the default links to display on the homepage.
For example the default as of this writing is this:

.. code:: python

    DJANGO_HOMEPAGE_LINKS=[
        ("Home", "/"),
        ("Posts", "/posts"),
        ("Tags", "/tags"),
        ("Collections", "/collections"),
    ]

The list must contain a series of lists or tuples with the first and values for each being the link
title and the URL respectively.

.. envvar:: DJANGO_SECRET_KEY

See the `Django docs <https://docs.djangoproject.com/en/6.0/ref/settings/#secret-key>`__ for details.
The application cannot start without setting this variable. Set it to a long alphanumeric string.
Preferably, 24 characters or more.

.. warning:: Failing to keep this value secret could lead to remote code execution and privilege escalation on the host system.

.. envvar:: DJANGO_SECURE_CONTENT_TYPE_NOSNIFF

TODO

.. envvar:: DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS

TODO

.. envvar:: DJANGO_SECURE_HSTS_PRELOAD

TODO

.. envvar:: DJANGO_SECURE_SSL_REDIRECT

TODO

.. envvar:: DJANGO_SERVER_EMAIL

TODO

.. envvar:: DJANGO_SETTINGS_MODULE

TODO

.. envvar:: DJANGO_SILKY_PYTHON_PROFILER_BINARY

TODO

.. envvar:: DJANGO_SILKY_PYTHON_PROFILER

TODO

.. envvar:: DJANGO_SOCIAL_LOGIN_ENABLED

TODO

.. envvar:: DJANGO_TITLE

TODO

.. envvar:: POSTGRES_DB

TODO

.. envvar:: POSTGRES_PASSWORD

TODO

.. envvar:: POSTGRES_PORT

TODO

.. envvar:: POSTGRES_USER

TODO

.. envvar:: USE_DOCKER

TODO
