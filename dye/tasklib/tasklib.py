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
import re
import sys
from datetime import datetime as dt
from datetime import timedelta
from os import path
from types import ModuleType

from .django import (collect_static, create_private_settings,
        _install_django_jenkins, link_local_settings, _manage_py,
        _manage_py_jenkins, clean_db, update_db, _infer_environment,
        create_uploads_dir, _setup_django_paths)

from .util import _check_call_wrapper, _call_wrapper, _rm_all_pyc, _create_link

# this is a global dictionary
from .environment import env

from fabric.operations import prompt


def _setup_paths(project_settings, localtasks):
    """Set up the paths used by other tasks"""
    # first merge in variables from project_settings - but ignore __doc__ etc
    user_settings = [x for x in vars(project_settings).keys() if not
                     (x.startswith('__') or callable(x) or isinstance(x, ModuleType))]
    for setting in user_settings:
        env.setdefault(setting, vars(project_settings)[setting])

    env.setdefault('localtasks', localtasks)
    # what is the root of the project - one up from this directory
    if 'local_vcs_root' in env:
        env['vcs_root_dir'] = env['local_vcs_root']
    else:
        env['vcs_root_dir'] = \
            path.abspath(path.join(env['deploy_dir'], os.pardir))

    if env['project_type'] in ["django", "cms"]:
        _setup_django_paths(env)

    _find_python(env)


def _find_python(env):
    python26 = path.join('/', 'usr', 'bin', 'python2.6')
    python27 = path.join('/', 'usr', 'bin', 'python2.7')
    generic_python = path.join('/', 'usr', 'bin', 'python')
    paths_to_try = (python27, python26, generic_python, sys.executable)
    chosen_python = None
    for python in paths_to_try:
        if path.exists(python):
            chosen_python = python
            break
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
        git_submodule_cmd = 'git submodule update --init --recursive'
        if env['quiet']:
            git_submodule_cmd += ' --quiet'
        else:
            print "### updating git submodules"
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


def gitlab(coverage=False):
    """Prepare the necessaries for Gitlab CI."""
    env['verbose'] = True

    create_private_settings()
    link_local_settings('gitlab')

    if hasattr(env['localtasks'], 'pre_deploy'):
        env['localtasks'].pre_deploy('gitlab')

    args = ['test', '-v']
    if coverage:
        args += ['--cov']
    _manage_py(args)


def deploy(environment=None):
    """Do all the required steps in order"""
    if environment:
        env['environment'] = environment
    else:
        env['environment'] = _infer_environment()
        if env['verbose']:
            print "Inferred environment as %s" % env['environment']

    if hasattr(env['localtasks'], 'pre_deploy'):
        env['localtasks'].pre_deploy(environment)

    create_private_settings()
    link_local_settings(env['environment'])
    update_git_submodules()
    update_db()

    collect_static(environment)

    if env['project_type'] in ["django", "cms"]:
        create_uploads_dir()

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


def _make_cron_name_safe(cron_file):
    safe_cron_re = r'[^a-zA-Z0-9_-]'
    safe_cron_file = re.sub(safe_cron_re, '', cron_file)
    if safe_cron_file != cron_file:
        print (
            "WARNING: Your cron file {} contains a '.' or other character "
            "that means it will be ignored by cron.  The link created is "
            "now called {}".format(cron_file, safe_cron_file)
        )
    return safe_cron_file


def link_cron_files():
    """ go through the cron directory in the root of the project and link cron
    files from there to the relevant directory in the /etc/cron* on the server

    So if the project contains:

        cron/cron.daily/my_daily_cronjob
        cron/cron.d/my_custom_cronjob

    They would be linked to:

        /etc/cron.daily/my_daily_cronjob
        /etc/cron.d/my_custom_cronjob

    We can also do some checks to make sure the files are executable and don't
    contain a . - as that means cron won't run them - http://askubuntu.com/a/111034/150
    """
    cron_dirs = ['cron.d', 'cron.daily', 'cron.hourly', 'cron.weekly', 'cron.monthly']
    for cron_dir in cron_dirs:
        vcs_cron_dir = path.join(env['vcs_root_dir'], 'cron', cron_dir)
        etc_cron_dir = path.join('/etc', cron_dir)
        if path.isdir(vcs_cron_dir):
            for cron_file in os.listdir(vcs_cron_dir):
                vcs_cron_file = path.join(vcs_cron_dir, cron_file)
                etc_cron_file = path.join(etc_cron_dir, _make_cron_name_safe(cron_file))
                if path.islink(etc_cron_file):
                    os.unlink(etc_cron_file)
                _create_link(vcs_cron_file, etc_cron_file)


def prune(num_days):
    """Do some cleaning up on the remote machine."""
    def _prune_db_dumps():
        PATH = '/var/django/%s/dbdumps/' % env['project_name']

        if not os.path.exists(PATH):
            print '%s does not exist, bailing out' % PATH
            return

        db_dumps_to_prune = []
        for dbdump in os.listdir(PATH):
            abs_path = os.path.join(PATH, dbdump)
            try:
                modified_int = os.path.getmtime(abs_path)
                modified_dt = dt.fromtimestamp(modified_int)
                prune_limit = dt.now() - timedelta(days=int(num_days))
                if modified_dt < prune_limit:
                    db_dumps_to_prune.append(abs_path)
            except os.error:
                print 'Failed to handle date wrangling for %s ' % abs_path

        if not db_dumps_to_prune:
            print 'Found 0 dumps to prune, bailing out'
            return

        print 'Discovered the following files for pruning: '
        for db_dump in db_dumps_to_prune:
            human_readable_time = str(dt.fromtimestamp(os.path.getmtime(db_dump)))
            print '%s with modified time of %s' % (db_dump, human_readable_time)
            print '\n'

        bail_out = False

        message = 'Would you like to continue with pruning? (yes/no)'
        answer = prompt(message, default='no', validate=r'^yes|no$')
        if answer == 'no':
            bail_out = True

        if bail_out is True:
            print 'Bailing out!'
            return

        for db_dump_abs_path in db_dumps_to_prune:
            os.remove(db_dump_abs_path)

    _prune_db_dumps()
