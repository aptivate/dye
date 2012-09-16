from fabric.api import env
from fabric import utils

# this is our common file that can be copied across projects
# we deliberately import all of this to get all the commands it
# provides as fabric commands
from fablib import *

# this is so we can call commands not imported by the above, basically
# commands that start with an underscore
import fablib

import os


# this function can just call the fablib _setup_path function
# or you can use it to override the defaults
def _local_setup():
    # put your own defaults here
    fablib._setup_path()
    # override settings here
    # if you have an ssh key and particular user you need to use
    # then uncomment the next 2 lines
    #env.user = "root" 
    #env.key_filename = ["/home/shared/keypair.rsa"]


def projectdir(project_dir=None):
    """ set the project directory so we can import project_settings (and localfab if it exists) """
    if not project_dir:
        project_dir = os.path.dirname(__file__)
    sys.path.append(project_dir)
    try:
        import project_settings
    except ImportError:
        print "Could not import project_settings from %s" % project_dir
        print "Cannot continue"
        sys.exit(1)
    fablib._setup_path(project_settings)
    if os.path.isfile(os.path.join(project_dir, 'localfab.py')):
        import localfab
        env.localfab = localfab

#
# These commands set up the environment variables
# to be used by later commands
#
def _server_setup(environment):
    if environment not in env.host_list:
        utils.abort('%s not defined in project_settings.host_list' % environment)
    env.environment = environment
    env.hosts = env.host_list[environment]
    _local_setup()

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


