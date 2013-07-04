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

from .exceptions import (InvalidArgumentError, InvalidProjectError,
                         TasksError)
from .database import _mysql_exec_as_root, db_exists, db_table_exists
from .django import (collect_static, create_private_settings,
        _install_django_jenkins, link_local_settings, _manage_py,
        _manage_py_jenkins)
from .util import (_check_call_wrapper, _call_wrapper, _rm_all_pyc,
        _call_command, CalledProcessError, _create_dir_if_not_exists)
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


def _get_django_db_settings(database='default'):
    """
        Args:
            database (string): The database key to use in the 'DATABASES'
                configuration. Override from the default to use a different
                database.
    """
    # import local_settings from the django dir. Here we are adding the django
    # project directory to the path. Note that env['django_dir'] may be more than
    # one directory (eg. 'django/project') which is why we use django_module
    sys.path.append(env['django_settings_dir'])
    import local_settings

    db_user = 'nouser'
    db_pw = 'nopass'
    db_host = '127.0.0.1'
    db_port = None
    # there are two ways of having the settings:
    # either as DATABASE_NAME = 'x', DATABASE_USER ...
    # or as DATABASES = { 'default': { 'NAME': 'xyz' ... } }
    try:
        db = local_settings.DATABASES[database]
        db_engine = db['ENGINE']
        db_name = db['NAME']
        if db_engine.endswith('mysql'):
            db_user = db['USER']
            db_pw = db['PASSWORD']
            db_port = db.get('PORT', db_port)
            db_host = db.get('HOST', db_host)

    except (AttributeError, KeyError):
        try:
            db_engine = local_settings.DATABASE_ENGINE
            db_name = local_settings.DATABASE_NAME
            if db_engine.endswith('mysql'):
                db_user = local_settings.DATABASE_USER
                db_pw = local_settings.DATABASE_PASSWORD
                db_port = getattr(local_settings, 'DATABASE_PORT', db_port)
                db_host = getattr(local_settings, 'DATABASE_HOST', db_host)
        except AttributeError:
            # we've failed to find the details we need - give up
            raise InvalidProjectError("Failed to find database settings")
    env['db_port'] = db_port
    env['db_host'] = db_host
    return (db_engine, db_name, db_user, db_pw, db_port, db_host)


def clean_db(database='default'):
    """Delete the database for a clean start"""
    # first work out the database username and password
    db_engine, db_name, db_user, db_pw, db_port, db_host = _get_django_db_settings(database=database)
    # then see if the database exists
    if db_engine.endswith('sqlite'):
        # delete sqlite file
        if path.isabs(db_name):
            db_path = db_name
        else:
            db_path = path.abspath(path.join(env['django_dir'], db_name))
        os.remove(db_path)
    elif db_engine.endswith('mysql'):
        # DROP DATABASE
        _mysql_exec_as_root('DROP DATABASE IF EXISTS %s' % db_name)

        test_db_name = 'test_' + db_name
        _mysql_exec_as_root('DROP DATABASE IF EXISTS %s' % test_db_name)


def _get_cache_table():
    # import settings from the django dir
    sys.path.append(env['django_settings_dir'])
    import settings
    if not hasattr(settings, 'CACHES'):
        return None
    if not settings.CACHES['default']['BACKEND'].endswith('DatabaseCache'):
        return None
    return settings.CACHES['default']['LOCATION']


def update_db(syncdb=True, drop_test_db=True, force_use_migrations=False, database='default'):
    """ create the database, and do syncdb and migrations
    Note that if syncdb is true, then migrations will always be done if one of
    the Django apps has a directory called 'migrations/'
    Args:
        syncdb (bool): whether to run syncdb (aswell as creating database)
        drop_test_db (bool): whether to drop the test database after creation
        force_use_migrations (bool): whether to force migrations, even when no
            migrations/ directories are found.
        database (string): The database value passed to _get_django_db_settings.
    """
    if not env['quiet']:
        print "### Creating and updating the databases"

    # first work out the database username and password
    db_engine, db_name, db_user, db_pw, db_port, db_host = _get_django_db_settings(database=database)

    # then see if the database exists
    if db_engine.endswith('mysql'):
        if not db_exists(db_user, db_pw, db_name, db_port, db_host):
            _mysql_exec_as_root('CREATE DATABASE %s CHARACTER SET utf8' % db_name)
            # we want to skip the grant when we are running fast tests -
            # when running mysql in RAM with --skip-grant-tables the following
            # line will give errors
            if env['environment'] != 'dev_fasttests':
                _mysql_exec_as_root(('GRANT ALL PRIVILEGES ON %s.* TO \'%s\'@\'localhost\' IDENTIFIED BY \'%s\'' %
                        (db_name, db_user, db_pw)))

        if not db_exists(db_user, db_pw, 'test_' + db_name, db_port, db_host):
            create_test_db(drop_after_create=drop_test_db, database=database)

    #print 'syncdb: %s' % type(syncdb)
    use_migrations = force_use_migrations
    if env['project_type'] == "django" and syncdb:
        # if we are using the database cache we need to create the table
        # and we need to do it before syncdb
        cache_table = _get_cache_table()
        if cache_table and not db_table_exists(cache_table,
                db_user, db_pw, db_name, db_port, db_host):
            _manage_py(['createcachetable', cache_table])
        # if we are using South we need to do the migrations aswell
        for app in env['django_apps']:
            if path.exists(path.join(env['django_dir'], app, 'migrations')):
                use_migrations = True
        _manage_py(['syncdb', '--noinput'])
        if use_migrations:
            _manage_py(['migrate', '--noinput'])


def create_test_db(drop_after_create=True, database='default'):
    db_engine, db_name, db_user, db_pw, db_port, db_host = _get_django_db_settings(database=database)

    test_db_name = 'test_' + db_name
    _mysql_exec_as_root('CREATE DATABASE %s CHARACTER SET utf8' % test_db_name)
    if env['environment'] != 'dev_fasttests':
        _mysql_exec_as_root(('GRANT ALL PRIVILEGES ON %s.* TO \'%s\'@\'localhost\' IDENTIFIED BY \'%s\'' %
            (test_db_name, db_user, db_pw)))
    if drop_after_create:
        _mysql_exec_as_root(('DROP DATABASE %s' % test_db_name))


def dump_db(dump_filename='db_dump.sql', for_rsync=False):
    """Dump the database in the current working directory"""
    db_engine, db_name, db_user, db_pw, db_port, db_host = _get_django_db_settings()
    if not db_engine.endswith('mysql'):
        raise InvalidArgumentError('dump_db only knows how to dump mysql so far')
    dump_cmd = [
        '/usr/bin/mysqldump',
        '--user=' + db_user,
        '--password=' + db_pw,
        '--host=' + db_host
    ]
    if db_port is not None:
        dump_cmd.append('--port=' + db_port)
    # this option will mean that there will be one line per insert
    # thus making the dump file better for rsync, but slightly bigger
    if for_rsync:
        dump_cmd.append('--skip-extended-insert')
    dump_cmd.append(db_name)

    dump_file = open(dump_filename, 'w')
    if env['verbose']:
        print 'Executing dump command: %s\nSending stdout to %s' % (' '.join(dump_cmd), dump_filename)
    _call_command(dump_cmd, stdout=dump_file)
    dump_file.close()


def restore_db(dump_filename):
    """Restore a database dump file by name"""
    db_engine, db_name, db_user, db_pw, db_port, db_host = _get_django_db_settings()
    if not db_engine.endswith('mysql'):
        raise InvalidProjectError('restore_db only knows how to restore mysql so far')
    restore_cmd = [
        '/usr/bin/mysql',
        '--user=' + db_user,
        '--password=' + db_pw,
        '--host=' + db_host
    ]
    if db_port is not None:
        restore_cmd.append('--port=' + db_port)
    restore_cmd.append(db_name)

    dump_file = open(dump_filename, 'r')
    if env['verbose']:
        print 'Executing dump command: %s\nSending stdin to %s' % (' '.join(restore_cmd), dump_filename)
    _call_command(restore_cmd, stdin=dump_file)
    dump_file.close()


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


def setup_db_dumps(dump_dir):
    """ set up mysql database dumps in root crontab """
    if not path.isabs(dump_dir):
        raise InvalidArgumentError('dump_dir must be an absolute path, you gave %s' % dump_dir)
    project_name = env['django_dir'].split('/')[-1]
    cron_file = path.join('/etc', 'cron.daily', 'dump_' + project_name)

    db_engine, db_name, db_user, db_pw, db_port, db_host = _get_django_db_settings()
    if db_engine.endswith('mysql'):
        _create_dir_if_not_exists(dump_dir)
        dump_file_stub = path.join(dump_dir, 'daily-dump-')

        # has it been set up already
        cron_set = True
        try:
            _check_call_wrapper('sudo crontab -l | grep mysqldump', shell=True)
        except CalledProcessError:
            cron_set = False

        if cron_set:
            return
        if path.exists(cron_file):
            return

        # write something like:
        # 30 1 * * * mysqldump --user=osiaccounting --password=aptivate --host=127.0.0.1 osiaccounting >  /var/osiaccounting/dumps/daily-dump-`/bin/date +\%d`.sql

        # don't use "with" for compatibility with python 2.3 on whov2hinari
        f = open(cron_file, 'w')
        try:
            f.write('#!/bin/sh\n')
            f.write('/usr/bin/mysqldump --user=%s --password=%s --host=%s --port=%s ' %
                    (db_user, db_pw, db_host, db_port))
            f.write('%s > %s' % (db_name, dump_file_stub))
            f.write(r'`/bin/date +\%d`.sql')
            f.write('\n')
        finally:
            f.close()

        os.chmod(cron_file, 0755)


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

    args = ['test', '-v0']

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


def _infer_environment():
    local_settings = path.join(env['django_settings_dir'], 'local_settings.py')
    if path.exists(local_settings):
        return os.readlink(local_settings).split('.')[-1]
    else:
        raise TasksError('no environment set, or pre-existing')


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
