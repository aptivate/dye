import os
import sys
from fabric.api import env

# deliberately import * - so fabric will treat it as a name
from fablib import *
# this is so we can call commands not imported by the above, basically
# commands that start with an underscore
import fablib

# Per project tasks can be defined in a file called localfab.py - we will
# import the functions from localfab.py if it exists. But first we need to
# know where to look.

# This fabfile can be called normally (in the same directory) or it can be
# installed as a python package, in which case the fab.py wrapper can call
# it from the directory that contains project_settings.py (and, optionally,
# localfab.py) It communicates which directory that is through an environment
# variable.
if 'DEPLOYDIR' in os.environ:
    # add the project directory to the python path, if set in environ
    sys.path.append(os.environ['DEPLOYDIR'])
    localfabdir = os.environ['DEPLOYDIR']
else:
    localfabdir = os.path.dirname(__file__)


# import the project settings
import project_settings

# valid environments - used for require statements in fablib
env.valid_envs = project_settings.host_list.keys()

#
# These commands set up the environment variables
# to be used by later commands
#
def _server_setup(environment):
    if environment not in project_settings.host_list:
        utils.abort('%s not defined in project_settings.host_list' % environment)
    env.environment = environment
    env.hosts = project_settings.host_list[environment]
    fablib._setup_paths(project_settings)


# Create automatic tasks for each environment in project_settings.host_list.
# These can be overridden by creating a function with the same name below,
# or in localfab.

for host in env.valid_envs:
    # http://stackoverflow.com/a/2776585/648162
    # This approach only defines specific functions, so it's less dangerous
    # than implementing __getattr__ on the module, and also produces the same
    # result every time, and allows importing and calling these default tasks
    # from localfab.

    # Also need to capture the value at the time the lambda is defined,
    # not when it's executed. http://stackoverflow.com/a/10452819/648162
    globals()[host] = lambda h=host: _server_setup(h)


def staging_test():
    """ use staging environment on remote host to run tests"""
    # this is on the same server as the customer facing stage site
    # so we need server_project_home to be different ...
    env.server_project_home = os.path.join(project_settings.server_home,
            env.project_name + '_test')

    env.webserver = None
    _server_setup('staging_test')


# now see if we can find localfab
# it is important to do this after importing from fablib, and after
# defining the above functions, so that functions in localfab can
# override those in fablib and fabfile.
#
# We deliberately don't surround the import by try/except. If there
# is an error in localfab, you want it to blow up immediately, rather
# than silently fail.
localfab = None
if os.path.isfile(os.path.join(localfabdir, 'localfab.py')):
    from localfab import *
