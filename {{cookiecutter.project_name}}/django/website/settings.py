# Django settings for {{project_name}} project.

# Build paths inside the project like this: path.join(BASE_DIR, ...)
from os import path
BASE_DIR = path.abspath(path.dirname(__file__))


########## DEFAULT DEBUG SETTINGS - OVERRIDE IN local_settings
DEBUG = True
TEMPLATE_DEBUG = DEBUG
##########


########## DATABASES are configured in local_settings.py.*


########## SECRET CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
import private_settings
SECRET_KEY = private_settings.SECRET_KEY
########## END SECRET CONFIGURATION


########## MANAGER/EMAIL CONFIGURATION
# These email addresses will get all the error email for the production server
# (and any other servers with DEBUG = False )
ADMINS = (
    ('Aptivate {{ cookiecutter.project_name }} team', '{{ cookiecutter.project_name }}-team@aptivate.org'),
    ('{{ cookiecutter.author_name }}', '{{ cookiecutter.email }}'),  # this is in case the above email doesn't work
)

MANAGERS = ADMINS

# these are the settings for production. We can override in the various
# local_settings if we want to
DEFAULT_FROM_EMAIL = 'donotreply@{{ cookiecutter.domain_name }}'
SERVER_EMAIL = 'server@{{ cookiecutter.domain_name }}'
########## MANAGER/EMAIL CONFIGURATION


########## GENERAL CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#time-zone
TIME_ZONE = 'Europe/London'

# See: https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = 'en'

LANGUAGES = [
    ('en', 'English'),
]

# See: https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-l10n
USE_L10N = True

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
########## END GENERAL CONFIGURATION


########## MEDIA CONFIGURATION
# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
# See: https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = path.join(BASE_DIR, 'uploads')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = '/uploads/'
########## END MEDIA CONFIGURATION


########## STATIC FILE CONFIGURATION
# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = path.join(BASE_DIR, 'static')

# URL prefix for static files.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = '/static/'

# See: https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    path.join(BASE_DIR, 'media'),
)

# See: https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)
########## END STATIC FILE CONFIGURATION

LOCALE_DIR = path.join(BASE_DIR, 'locale')
if path.isdir(LOCALE_DIR):
    LOCALE_PATHS = (LOCALE_DIR,)

########## APP CONFIGURATION
DJANGO_APPS = (
    # Default Django apps:
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Useful template tags:
    # 'django.contrib.humanize',

    # Admin
    'django.contrib.admin',
)
THIRD_PARTY_APPS = (
    'south',  # Database migration helpers:
    #{% if cookiecutter.django_type == "normal" or cookiecutter.django_type == "cms" %}
    'crispy_forms',  # Form layouts
    'django_extensions',
    'easy_thumbnails',
    'registration',
    'haystack',
    #{% endif %}
    #{% if cookiecutter.django_type == "cms" %}
    'cms',
    'mptt',
    'menus',
    'sekizai',
    'filer',
    'cms.plugins.link',
    'cms.plugins.snippet',
    'cms.plugins.googlemap',
    'cmsplugin_filer_file',
    'cmsplugin_filer_folder',
    'cmsplugin_filer_image',
    'cmsplugin_filer_teaser',
    'cmsplugin_filer_video',
    'cms_redirects',
    'reversion',
    'djangocms_text_ckeditor',  # must load after Django CMS
    #{% endif %}
)

# Apps specific for this project go here.
LOCAL_APPS = (
    # Your stuff: custom apps go here
)

# See: https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
########## END APP CONFIGURATION


########## MIDDLEWARE CONFIGURATION
MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    #{% if cookiecutter.django_type == "cms" %} cms stuff
    'cms.middleware.user.CurrentUserMiddleware',
    'cms.middleware.page.CurrentPageMiddleware',
    'cms.middleware.toolbar.ToolbarMiddleware',
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',
    'cms_redirects.middleware.RedirectFallbackMiddleware',
    #{% endif %}
)
########## END MIDDLEWARE CONFIGURATION


########## URL Configuration
ROOT_URLCONF = 'urls'

# Python dotted path to the WSGI application used by Django's runserver.
# WSGI_APPLICATION = 'wsgi.application'
########## END URL Configuration


########## django-secure - intended for sites that use SSL
SECURE = False
if SECURE:
    INSTALLED_APPS += ("djangosecure", )

    # set this to 60 seconds and then to 518400 when you can prove it works
    SECURE_HSTS_SECONDS = 60
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_FRAME_DENY = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SECURE_SSL_REDIRECT = True
########## end django-secure


########## AUTHENTICATION CONFIGURATION
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    #"allauth.account.auth_backends.AuthenticationBackend",
)

# Some really nice defaults
#ACCOUNT_AUTHENTICATION_METHOD = "username"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
########## END AUTHENTICATION CONFIGURATION


#{% if cookiecutter.django_type == "normal" or cookiecutter.django_type == "cms" %}######### HAYSTACK SEARCH CONFIGURATION
HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.elasticsearch_backend.ElasticsearchSearchEngine',
        'URL': 'http://127.0.0.1:9200/',
        'INDEX_NAME': '{{ cookiecutter.project_name }}',
    },
}

HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'
HAYSTACK_SEARCH_RESULTS_PER_PAGE = 1000
########## END HAYSTACK SEARCH CONFIGURATION
#{% endif %}

########## Custom user app defaults
# Select the correct user model
#AUTH_USER_MODEL = "users.User"
#LOGIN_REDIRECT_URL = "users:redirect"
########## END Custom user app defaults


########## SLUGLIFIER
#AUTOSLUG_SLUGIFY_FUNCTION = "slugify.slugify"
########## END SLUGLIFIER


########## LOGGING CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#logging
# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            # 'formatter': 'simple'
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        '': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    }
}
########## END LOGGING CONFIGURATION


########## BINDER STUFF
# Usually included by adding intranet_binder as a git submodule
# The name of the class to use to run the test suite
# TEST_RUNNER = 'intranet_binder.testing.SmartTestSuiteRunner'

#MONKEY_PATCHES = ['intranet_binder.monkeypatches']
########## END BINDER STUFF


#{% if cookiecutter.django_type == "cms" %}
# https://django-filer.readthedocs.org/en/0.8.3/getting_started.html#configuration
THUMBNAIL_PROCESSORS = (
    'easy_thumbnails.processors.colorspace',
    'easy_thumbnails.processors.autocrop',
    #'easy_thumbnails.processors.scale_and_crop',
    'filer.thumbnail_processors.scale_and_crop_with_subject_location',
    'easy_thumbnails.processors.filters',
)
#{% endif %}


# this section allows us to do a deep update of dictionaries
import collections
from copy import deepcopy


def update_recursive(dest, source):
    for k, v in source.iteritems():
        if dest.get(k, None) and isinstance(v, collections.Mapping):
            update_recursive(dest[k], source[k])
        else:
            dest[k] = deepcopy(source[k])

########## LOCAL_SETTINGS
# tasks.py expects to find local_settings.py so the database stuff is there
#--------------------------------
# local settings import
#from http://djangosnippets.org/snippets/1873/
#--------------------------------
try:
    import local_settings
except ImportError:
    print """
    -------------------------------------------------------------------------
    You need to create a local_settings.py file. Run ../../deploy/tasks.py
    deploy:<whatever> to use one of the local_settings.py.* files as your
    local_settings.py, and create the database and tables mentioned in it.
    -------------------------------------------------------------------------
    """
    import sys
    sys.exit(1)
else:
    # Import any symbols that begin with A-Z. Append to lists, or update
    # dictionaries for any symbols that begin with "EXTRA_".
    import re
    for attr in dir(local_settings):
        match = re.search('^EXTRA_(\w+)', attr)
        if match:
            name = match.group(1)
            value = getattr(local_settings, attr)
            try:
                original = globals()[name]
                if isinstance(original, collections.Mapping):
                    update_recursive(original, value)
                else:
                    original += value
            except KeyError:
                globals()[name] = value
        elif re.search('^[A-Z]', attr):
            globals()[attr] = getattr(local_settings, attr)

    CELERY_RESULT_BACKEND = "database"
    default_db = DATABASES['default']  # pyflakes: ignore
    CELERY_RESULT_DBURI = "mysql://{0}:{1}@{2}:{3}/{4}".format(
        default_db['USER'], default_db['PASSWORD'], default_db['HOST'],
        default_db['PORT'], default_db['NAME'])
########## END LOCAL_SETTINGS


##### from here on is stuff that depends on the value of DEBUG
##### which is set in LOCAL_SETTINGS


if DEBUG is False:
    ########## SITE CONFIGURATION
    # Hosts/domain names that are valid for this site
    # See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
    #ALLOWED_HOSTS = ["*"]
    ALLOWED_HOSTS = [
        '.{{ cookiecutter.domain_name }}',
        'www.{{ cookiecutter.domain_name }}',
        'fen-vz-{{ cookiecutter.project_name }}-stage.fen.aptivate.org',
        'fen-vz-{{ cookiecutter.project_name }}-dev.fen.aptivate.org',
        '{{ cookiecutter.project_name }}.dev.aptivate.org',
        '{{ cookiecutter.project_name }}.stage.aptivate.org',
    ]
    ########## END SITE CONFIGURATION

########## TEMPLATE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.core.context_processors.tz',
    'django.contrib.messages.context_processors.messages',
    'django.core.context_processors.request',
    # Your stuff: custom template context processers go here
    #{% if cookiecutter.django_type == "cms" %} cms stuff
    'cms.context_processors.media',
    'sekizai.context_processors.sekizai',
    #{% endif %}
)


# See: https://docs.djangoproject.com/en/dev/ref/settings/#template-dirs
TEMPLATE_DIRS = (
    path.join(BASE_DIR, 'templates'),
)

if DEBUG:
    TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )
else:
    TEMPLATE_LOADERS = (
        ('django.template.loaders.cached.Loader', (
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        )),
    )
########## END TEMPLATE CONFIGURATION


########## Your stuff: Below this line define 3rd party libary settings
