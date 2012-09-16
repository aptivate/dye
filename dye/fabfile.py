from fabric.api import env
from fabric import main, state, utils

# this is so we can call commands not imported by the above, basically
# commands that start with an underscore
import fablib
import os, sys

def _add_commands_from_module(mod):
    docstring, new_style, classic, default = main.load_tasks_from_module(mod)
    # for now we are using classic style fabric tasks - add them to the commands
    state.commands.update(classic)

def projectdir(project_dir=None):
    """ set the project directory so we can import project_settings (and localfab if it exists) """
    if not project_dir:
        project_dir = os.path.dirname(__file__)
    sys.path.append(project_dir)
    # first import the project settings
    try:
        import project_settings
    except ImportError:
        print "Could not import project_settings from %s" % project_dir
        print "Cannot continue"
        sys.exit(1)
    fablib._setup_path(project_settings)

    # Now add the extra fabric commands
    # add fablib first, then localfab can overwrite it
    _add_commands_from_module(fablib)
    # if the file exists we should be able to import it - if the import raises
    # an exception, we WANT to blow up here
    if os.path.isfile(os.path.join(project_dir, 'localfab.py')):
        import localfab
        _add_commands_from_module(localfab)

#
# These commands set up the environment variables
# to be used by later commands
#
def _server_setup(environment):
    if environment not in env.host_list:
        utils.abort('%s not defined in project_settings.host_list' % environment)
    env.environment = environment
    env.hosts = env.host_list[environment]

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


