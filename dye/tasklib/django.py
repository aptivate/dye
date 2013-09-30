import os
from os import path
import sys
import random
import subprocess

from .exceptions import TasksError
from .database import get_db_manager
from .exceptions import InvalidProjectError, ShellCommandError
from .util import _check_call_wrapper
# global dictionary for state
from .environment import env


def _manage_py(args, cwd=None):
    # for manage.py, always use the system python
    # otherwise the update_ve will fail badly, as it deletes
    # the virtualenv part way through the process ...
    manage_cmd = [env['python_bin'], env['manage_py']]
    if env['quiet']:
        manage_cmd.append('--verbosity=0')
    if isinstance(args, str):
        manage_cmd.append(args)
    else:
        manage_cmd.extend(args)

    # Allow manual specification of settings file
    if 'manage_py_settings' in env:
        manage_cmd.append('--settings=%s' % env['manage_py_settings'])

    if cwd is None:
        cwd = env['django_dir']

    if env['verbose']:
        print 'Executing manage command: %s' % ' '.join(manage_cmd)
    output_lines = []
    try:
        # TODO: make compatible with python 2.3
        popen = subprocess.Popen(manage_cmd, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    except OSError, e:
        print "Failed to execute command: %s: %s" % (manage_cmd, e)
        raise e
    for line in iter(popen.stdout.readline, ""):
        if env['verbose']:
            print line,
        output_lines.append(line)
    returncode = popen.wait()
    if returncode != 0:
        error_msg = "Failed to execute command: %s: returned %s\n%s" % \
            (manage_cmd, returncode, "\n".join(output_lines))
        raise ShellCommandError(error_msg, popen.returncode)
    return output_lines


def _infer_environment():
    local_settings = path.join(env['django_settings_dir'], 'local_settings.py')
    if path.exists(local_settings):
        return os.readlink(local_settings).split('.')[-1]
    else:
        raise TasksError('no environment set, or pre-existing')


def _create_db_objects(database='default'):
    """
        Args:
            database (string): The database key to use in the 'DATABASES'
                configuration. Override from the default to use a different
                database.
    """
    if 'db' in env:
        return
    # work out what the environment is if necessary
    if 'environment' not in env:
        env['environment'] = _infer_environment()

    # import local_settings from the django dir. Here we are adding the django
    # project directory to the path. Note that env['django_dir'] may be more than
    # one directory (eg. 'django/project') which is why we use django_module
    sys.path.append(env['django_settings_dir'])
    import local_settings

    default_host = '127.0.0.1'
    db_details = {}
    # there are two ways of having the settings:
    # either as DATABASE_NAME = 'x', DATABASE_USER ...
    # or as DATABASES = { 'default': { 'NAME': 'xyz' ... } }
    try:
        db = local_settings.DATABASES[database]
        db_details['engine'] = db['ENGINE']
        db_details['name'] = db['NAME']
        if db_details['engine'].endswith('sqlite'):
            db_details['root_dir'] = env['django_dir']
        else:
            db_details['user'] = db['USER']
            db_details['password'] = db['PASSWORD']
            db_details['port'] = db.get('PORT', None)
            db_details['host'] = db.get('HOST', default_host)

    except (AttributeError, KeyError):
        try:
            db_details['engine'] = local_settings.DATABASE_ENGINE
            db_details['name'] = local_settings.DATABASE_NAME
            if db_details['engine'].endswith('sqlite'):
                db_details['root_dir'] = env['django_dir']
            else:
                db_details['user'] = local_settings.DATABASE_USER
                db_details['password'] = local_settings.DATABASE_PASSWORD
                db_details['port'] = getattr(local_settings, 'DATABASE_PORT', None)
                db_details['host'] = getattr(local_settings, 'DATABASE_HOST', default_host)
        except AttributeError:
            # we've failed to find the details we need - give up
            raise InvalidProjectError("Failed to find database settings")
    # sort out the engine part - discard everything before the last .
    db_details['engine'] = db_details['engine'].split('.')[-1]
    if env['environment'] == 'dev_fasttests':
        db['grant_enabled'] = False
    # and create the objects that hold the db details
    env['db'] = get_db_manager(**db_details)
    # and the test db object
    db_details['name'] = 'test_' + db_details['name']
    env['test_db'] = get_db_manager(**db_details)


def clean_db(database='default'):
    """Delete the database for a clean start"""
    _create_db_objects(database=database)
    env['db'].drop_db()
    env['test_db'].drop_db()


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

    _create_db_objects(database=database)

    # then see if the database exists
    env['db'].ensure_user_and_db_exist()
    if not drop_test_db:
        env['test_db'].create_db_if_not_exists()
    env['test_db'].grant_all_privileges_for_database()

    #print 'syncdb: %s' % type(syncdb)
    use_migrations = force_use_migrations
    if env['project_type'] == "django" and syncdb:
        # if we are using the database cache we need to create the table
        # and we need to do it before syncdb
        cache_table = _get_cache_table()
        if cache_table and not env['db'].test_db_table_exists(cache_table):
            _manage_py(['createcachetable', cache_table])
        # if we are using South we need to do the migrations aswell
        for app in env['django_apps']:
            if path.exists(path.join(env['django_dir'], app, 'migrations')):
                use_migrations = True
        _manage_py(['syncdb', '--noinput'])
        if use_migrations:
            _manage_py(['migrate', '--noinput'])


def create_test_db(drop_after_create=True, database='default'):
    _create_db_objects(database=database)
    env['test_db'].create_db_if_not_exists(drop_after_create=drop_after_create)


def dump_db(dump_filename='db_dump.sql', for_rsync=False, database='default'):
    _create_db_objects(database=database)
    env['db'].dump_db(dump_filename, for_rsync)


def restore_db(dump_filename='db_dump.sql', database='default'):
    _create_db_objects(database=database)
    env['db'].restore_db(dump_filename)


def create_dbdump_cron_file(cron_file, dump_file_stub, database='default'):
    _create_db_objects(database=database)
    env['db'].create_dbdump_cron_file(cron_file, dump_file_stub)


def setup_db_dumps(dump_dir, database='default'):
    _create_db_objects(database=database)
    env['db'].setup_db_dumps(dump_dir)


def link_local_settings(environment):
    """ link local_settings.py.environment as local_settings.py """
    if not env['quiet']:
        print "### creating link to local_settings.py"

    # check that settings imports local_settings, as it always should,
    # and if we forget to add that to our project, it could cause mysterious
    # failures
    settings_file_path = path.join(env['django_settings_dir'], 'settings.py')
    if not(path.isfile(settings_file_path)):
        raise InvalidProjectError("Fatal error: settings.py doesn't seem to exist")
    with open(settings_file_path) as settings_file:
        matching_lines = [line for line in settings_file if 'local_settings' in line]
    if not matching_lines:
        raise InvalidProjectError("Fatal error: settings.py doesn't seem to import "
            "local_settings.*: %s" % settings_file_path)

    source = path.join(env['django_settings_dir'], 'local_settings.py.%s' %
        environment)
    target = path.join(env['django_settings_dir'], 'local_settings.py')

    # die if the correct local settings does not exist
    if not path.exists(source):
        raise InvalidProjectError("Could not find file to link to: %s" % source)

    # remove any old versions, plus the pyc copy
    for old_file in (target, target + 'c'):
        if path.exists(old_file):
            os.remove(old_file)

    if os.name == 'posix':
        os.symlink('local_settings.py.%s' % environment, target)
    elif os.name == 'nt':
        try:
            import win32file
        except ImportError:
            raise Exception(
                "It looks like the PyWin32 extensions are not installed")
        try:
            win32file.CreateSymbolicLink(target, source)
        except NotImplementedError:
            win32file.CreateHardLink(target, source)
    else:
        import shutil
        shutil.copy2(source, target)
    env['environment'] = environment


def create_private_settings():
    """ create private settings file
    - contains generated DB password and secret key"""
    private_settings_file = path.join(env['django_settings_dir'],
                                    'private_settings.py')
    if not path.exists(private_settings_file):
        if not env['quiet']:
            print "### creating private_settings.py"
        # don't use "with" for compatibility with python 2.3 on whov2hinari
        f = open(private_settings_file, 'w')
        try:
            secret_key = "".join([random.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for i in range(50)])
            db_password = "".join([random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for i in range(12)])

            f.write("SECRET_KEY = '%s'\n" % secret_key)
            f.write("DB_PASSWORD = '%s'\n" % db_password)
        finally:
            f.close()
        # need to think about how to ensure this is owned by apache
        # despite having been created by root
        #os.chmod(private_settings_file, 0400)


def collect_static():
    return _manage_py(["collectstatic", "--noinput"])


def _install_django_jenkins():
    """ ensure that pip has installed the django-jenkins thing """
    if not env['quiet']:
        print "### Installing Jenkins packages"
    pip_bin = path.join(env['ve_dir'], 'bin', 'pip')
    cmds = [
        [pip_bin, 'install', 'django-jenkins'],
        [pip_bin, 'install', 'pylint'],
        [pip_bin, 'install', 'coverage']]

    for cmd in cmds:
        _check_call_wrapper(cmd)


def _manage_py_jenkins():
    """ run the jenkins command """
    args = ['jenkins', ]
    args += ['--pylint-rcfile', path.join(env['vcs_root_dir'], 'jenkins', 'pylint.rc')]
    coveragerc_filepath = path.join(env['vcs_root_dir'], 'jenkins', 'coverage.rc')
    if path.exists(coveragerc_filepath):
        args += ['--coverage-rcfile', coveragerc_filepath]
    args += env['django_apps']
    if not env['quiet']:
        print "### Running django-jenkins, with args; %s" % args
    _manage_py(args, cwd=env['vcs_root_dir'])
