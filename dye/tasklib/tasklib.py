# This script is to set up various things for our projects. It can be used by:
#
# * developers - setting up their own environment
# * jenkins - setting up the environment and running tests
# * fabric - it will call a copy on the remote server when deploying
#
# The tasks it will do (eventually) include:
#
# * creating, updating and deleting the virtualenv
# * creating, updating and deleting the database (sqlite or mysql)
# * setting up the local_settings stuff
# * running tests
"""This script is to set up various things for our projects. It can be used by:

* developers - setting up their own environment
* jenkins - setting up the environment and running tests
* fabric - it will call a copy on the remote server when deploying

"""

import os
from os import path
import sys

from .django import (collect_static, create_private_settings,
        _install_django_jenkins, link_local_settings, _manage_py,
        _manage_py_jenkins, clean_db, update_db, _infer_environment)
from .util import (_check_call_wrapper,
                   _call_wrapper,
                   _rm_all_pyc,
                   _capture_command)
# this is a global dictionary
from .environment import env


def _setup_paths(project_settings, localtasks):
    """Set up the paths used by other tasks"""
    # first merge in variables from project_settings - but ignore __doc__ etc
    user_settings = [x for x in vars(project_settings).keys() if not x.startswith('__')]
    for setting in user_settings:
        env.setdefault(setting, vars(project_settings)[setting])

    env.setdefault('localtasks', localtasks)
    # what is the root of the project - one up from this directory
    if 'local_vcs_root' in env:
        env['vcs_root_dir'] = env['local_vcs_root']
    else:
        env['vcs_root_dir'] = \
            path.abspath(path.join(env['deploy_dir'], os.pardir))

    # the django settings will be in the django_dir for old school projects
    # otherwise it should be defined in the project_settings
    env.setdefault('relative_django_settings_dir', env['relative_django_dir'])
    env.setdefault('relative_ve_dir', path.join(env['relative_django_dir'], '.ve'))

    # now create the absolute paths of everything else
    env.setdefault('django_dir',
                   path.join(env['vcs_root_dir'], env['relative_django_dir']))
    env.setdefault('django_settings_dir',
                   path.join(env['vcs_root_dir'], env['relative_django_settings_dir']))
    env.setdefault('ve_dir',
                   path.join(env['vcs_root_dir'], env['relative_ve_dir']))
    env.setdefault('manage_py', path.join(env['django_dir'], 'manage.py'))

    python26 = path.join('/', 'usr', 'bin', 'python2.6')
    python27 = path.join('/', 'usr', 'bin', 'python2.7')
    generic_python = path.join('/', 'usr', 'bin', 'python')
    paths_to_try = (python26, python27, generic_python, sys.executable)
    chosen_python = None
    for python in paths_to_try:
        if path.exists(python):
            chosen_python = python
    if chosen_python is None:
        raise Exception("Failed to find a valid Python executable " +
                "in any of these locations: %s" % paths_to_try)
    if env['verbose']:
        print "Using Python from %s" % chosen_python
    env.setdefault('python_bin', chosen_python)


def update_git_submodules():
    """If this is a git project then check for submodules and update"""
    git_modules_file = path.join(env['vcs_root_dir'], '.gitmodules')
    if path.exists(git_modules_file):
        if not env['quiet']:
            print "### updating git submodules"
            git_submodule_cmd = 'git submodule update --init'
        else:
            git_submodule_cmd = 'git submodule --quiet update --init'
        _check_call_wrapper(git_submodule_cmd, cwd=env['vcs_root_dir'], shell=True)


def run_tests(*extra_args):
    """Run the django tests.

    With no arguments it will run all the tests for you apps (as listed in
    project_settings.py), but you can also pass in multiple arguments to run
    the tests for just one app, or just a subset of tests. Examples include:

    ./tasks.py run_tests:myapp
    ./tasks.py run_tests:myapp.ModelTests,myapp.ViewTests.my_view_test
    """
    if not env['quiet']:
        print "### Running tests"

    args = ['test', '--noinput', '-v0']

    if extra_args:
        args += extra_args
    else:
        # default to running all tests
        args += env['django_apps']

    _manage_py(args)


def quick_test(*extra_args):
    """Run the django tests with local_settings.py.dev_fasttests

    local_settings.py.dev_fasttests (should) use port 3307 so it will work
    with a mysqld running with a ramdisk, which should be a lot faster. The
    original environment will be reset afterwards.

    With no arguments it will run all the tests for you apps (as listed in
    project_settings.py), but you can also pass in multiple arguments to run
    the tests for just one app, or just a subset of tests. Examples include:

    ./tasks.py quick_test:myapp
    ./tasks.py quick_test:myapp.ModelTests,myapp.ViewTests.my_view_test
    """
    original_environment = _infer_environment()

    try:
        link_local_settings('dev_fasttests')
        update_db()
        run_tests(*extra_args)
    finally:
        link_local_settings(original_environment)


def run_jenkins():
    """ make sure the local settings is correct and the database exists """
    env['verbose'] = True
    # don't want any stray pyc files causing trouble
    _rm_all_pyc()
    _install_django_jenkins()
    create_private_settings()
    link_local_settings('jenkins')
    clean_db()
    update_db()
    _manage_py_jenkins()


def deploy(environment=None):
    """Do all the required steps in order"""
    if environment:
        env['environment'] = environment
    else:
        env['environment'] = _infer_environment()
        if env['verbose']:
            print "Inferred environment as %s" % env['environment']

    create_private_settings()
    link_local_settings(env['environment'])
    update_git_submodules()
    update_db()

    collect_static()

    if hasattr(env['localtasks'], 'post_deploy'):
        env['localtasks'].post_deploy(env['environment'])

    print "\n*** Finished deploying %s for %s." % (
            env['project_name'], env['environment'])


def patch_south():
    """ patch south to fix pydev errors """
    python = 'python2.6'
    if '2.7' in env['python_bin']:
        python = 'python2.7'
    south_db_init = path.join(env['ve_dir'],
                'lib/%s/site-packages/south/db/__init__.py' % python)
    patch_file = path.join(
        path.dirname(__file__), os.pardir, 'patch', 'south.patch')
    # check if patch already applied - patch will fail if it is
    patch_applied = _call_wrapper(['grep', '-q', 'pydev', south_db_init])
    if patch_applied != 0:
        cmd = ['patch', '-N', '-p0', south_db_init, patch_file]
        _check_call_wrapper(cmd)
