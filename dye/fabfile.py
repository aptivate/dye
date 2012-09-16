import os, sys
from fabric.api import env
from fabric import main, state, utils

# deliberately import * - so fabric will treat it as a name
from fablib import *

# add the project directory to the python path
if 'PROJECTDIR' not in os.environ:
    print 'We need to know where the project directory is'
    print 'for project_settings.py, and the optional localfab.py'
    print 'Please use the fab.py wrapper script'
    sys.exit(1)
sys.path.append(os.environ['PROJECTDIR'])

# now see if we can find localfab
# it is important to do this after importing from fablib, so that
# function in localfab can override those in fablib
if os.path.isfile(os.path.join(os.environ['PROJECTDIR'], 'localfab.py')):
    from localfab import *

# this is so we can call commands not imported by the above, basically
# commands that start with an underscore
import fablib

# import the project settings
import project_settings

#
# These commands set up the environment variables
# to be used by later commands
#
def _server_setup(environment):
    if environment not in env.host_list:
        utils.abort('%s not defined in project_settings.host_list' % environment)
    env.environment = environment
    env.hosts = env.host_list[environment]
    fablib._setup_path(project_settings)

def dev_server():
    """ use dev environment on remote host to play with code in production-like env"""
    _server_setup('dev_server')


def staging_test():
    """ use staging environment on remote host to run tests"""
    # this is on the same server as the customer facing stage site
    # so we need project_root to be different ...
    env.project_dir = env.project_name + '_test'
    env.use_apache = False
    _server_setup('staging_test')


def staging():
    """ use staging environment on remote host to demo to client"""
    _server_setup('staging')


def production():
    """ use production environment on remote host"""
    _server_setup('production')


