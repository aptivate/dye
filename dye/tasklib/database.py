import os
from os import path
import MySQLdb

from .exceptions import InvalidArgumentError, InvalidProjectError
from .util import (_check_call_wrapper, _capture_command,
                   _call_command, _create_dir_if_not_exists, CalledProcessError,
                   _ask_for_password, _get_file_contents)

# this is a global dictionary
from .environment import env

root_pw_file = '/root/mysql_root_password'
root_pw_file_needs_sudo = True

# a global dictionary for database details
db_details = {
    'engine': None,
    'name': None,
    'user': None,
    'password': None,
    'port': None,
    'host': None,
    'root_password': None,
    'grant_enabled': True,   # want to disable this when running in RAM
}

# connections to the MySQL database for the normal user and the root user
user_db_conn = None
root_db_conn = None


def _reset_db_details():
    """Reset the db_details global to the default, empty state."""
    global db_details
    db_details = {
        'engine': None,
        'name': None,
        'user': None,
        'password': None,
        'port': None,
        'host': None,
        'root_password': None,
        'grant_enabled': True,   # want to disable this when running in RAM
    }


def _get_db_details():
    """This could be overridden (by monkey patching).
    Alternatively you could set db_details values before calling any functions
    in this file."""
    if db_details['engine'] is None:
        raise Exception("Don't know how to find database details")
    return db_details


def _get_mysql_root_password():
    """This can be overridden (by monkeypatching) if required."""
    # first try to read the root password from a file
    # otherwise ask the user
    if db_details['root_password'] is None:
        root_pw = _get_file_contents(root_pw_file, sudo=root_pw_file_needs_sudo)
        # maybe it is wrong (on developer machine) - check it
        if root_pw is not None and not _test_mysql_root_password(root_pw):
            if env['verbose']:
                print "mysql root password in %s doesn't work" % root_pw_file
            root_pw = None

        # still haven't got it, ask the user
        if root_pw is None and not env['quiet']:
            root_pw = _ask_for_password("", test_fn=_test_mysql_root_password)

        # now we have root password that works
        db_details['root_password'] = root_pw

    return db_details['root_password']


def _create_db_connection(**kwargs):
    if db_details['host']:
        kwargs.set_default('host', db_details['host'])
    if db_details['port']:
        kwargs.set_default('port', db_details['port'])
    return MySQLdb.connect(**kwargs)


def _get_user_db_cursor(**cursor_kwargs):
    global user_db_conn
    if user_db_conn is None:
        user_db_conn = _create_db_connection(
            user=db_details['user'],
            passwd=db_details['password'],
            db=db_details['name']
        )
    return user_db_conn.cursor(**cursor_kwargs)


def _close_user_db_connection():
    global user_db_conn
    if user_db_conn is not None:
        user_db_conn.close()
        user_db_conn = None


def _get_root_db_cursor(**cursor_kwargs):
    global root_db_conn
    if root_db_conn is None:
        root_db_conn = _create_db_connection(
            user='root', password=_get_mysql_root_password())
    return root_db_conn.cursor(**cursor_kwargs)


def _close_root_db_connection():
    global root_db_conn
    if root_db_conn is not None:
        root_db_conn.close()
        root_db_conn = None


def _create_mysql_args(db_name=None):
    user = db_details['user']
    password = db_details['password']
    if db_name is None:
        db_name = db_details['name']

    mysql_args = [
        '-u', user,
        '-p%s' % password,
    ]
    if db_details['host']:
        mysql_args.append('--host=%s' % db_details['host'])
    if db_details['port']:
        mysql_args.append('--port=%s' % db_details['port'])
    mysql_args.append(db_name)
    return mysql_args


def _mysql_exec(mysql_cmd, db_name=None, capture_output=False):
    """execute a SQL statement using the mysql command line client.
    We do this rather than using the python libraries so this script can be
    run without the python libraries being installed.  (Also this was orginally
    written for fabric, so the code was already proven there)."""
    mysql_call = ['mysql'] + _create_mysql_args(db_name)
    mysql_call += ['-e', mysql_cmd]

    if capture_output:
        return _capture_command(mysql_call)
    else:
        _check_call_wrapper(mysql_call)


def _mysql_exec_as_root(mysql_cmd_list, root_password=None):
    """ execute a SQL statement using MySQL as the root MySQL user"""
    cursor = _get_root_db_cursor()
    try:
        for cmd in mysql_cmd_list:
            cursor.execute(cmd)
    finally:
        cursor.close()


def _test_mysql_user_exists(user=None):
    # check user in mysql table
    if not user:
        user = db_details['user']
    cursor = _get_root_db_cursor()
    try:
        rows = cursor.execute("SELECT 1 FROM mysql.user WHERE user = '%s'" % user)
    finally:
        cursor.close()
    return rows != 0


def _test_mysql_user_password_works(user=None, password=None):
    # try to connect
    if not user:
        user = db_details['user']
    if not password:
        password = db_details['password']
    kwargs = {
        'user': user,
        'passwd': password,
    }
    try:
        db_conn = _create_db_connection(**kwargs)
    except MySQLdb.OperationalError as e:
        if e.args[0] == 1045:  # access denied for user/password
            return False
        else:
            raise e
    db_conn.close()
    return True


def _test_mysql_root_password(password):
    """Try a no-op with the root password"""
    return _test_mysql_user_password_works(user='root', password=password)


def _db_exists(db_name):
    cursor = _get_root_db_cursor()
    try:
        cursor.execute("SHOW DATABASES")
        db_list = [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
    return db_name in db_list


def _db_table_exists(table_name):
    cursor = _get_user_db_cursor()
    try:
        rows = cursor.execute("SHOW TABLES WHERE LIKE %s" % table_name)
    finally:
        cursor.close()
    return rows != 0


def _create_user_if_not_exists(user=None, password=None):
    if user is None:
        user = db_details['user']
    if password is None:
        password = db_details['password']
    host = db_details.get('host', 'localhost')
    if not _test_mysql_user_exists(user):
        _mysql_exec_as_root(
            [
                "CREATE USER '%s'@'%s' IDENTIFIED BY '%s'" %
                           (user, host, password),
            ]
        )


def _set_user_password(user=None, password=None):
    if user is None:
        user = db_details['user']
    if password is None:
        password = db_details['password']
    host = db_details.get('host', 'localhost')
    _mysql_exec_as_root(
        [
            "SET PASSWORD FOR USER '%s'@'%s' = PASSWORD('%s')" %
                (user, host, password),
        ]
    )


def grant_all_privileges_for_database(db_name=None, user=None):
    if not db_details['grant_enabled']:
        return
    if db_name is None:
        db_name = db_details['name']
    if user is None:
        user = db_details['user']
    host = db_details.get('host', 'localhost')

    _mysql_exec_as_root(
        [
            "GRANT ALL PRIVILEGES ON %s.* TO '%s'@'%s'" %
                (db_name, user, host),
            "FLUSH PRIVILEGES",
        ]
    )


def create_db_if_not_exists(db_name=None):
    if db_name is None:
        db_name = db_details['name']

    if not _db_exists(db_name):
        _mysql_exec_as_root('CREATE DATABASE %s CHARACTER SET utf8' % db_name)


def ensure_user_and_db_exist(user=None, password=None, db_name=None):
    if user is None:
        user = db_details['user']
    if password is None:
        password = db_details['password']
    if db_name is None:
        db_name = db_details['name']
    # the below just make sure things line up at the end of the process
    # TODO: should we do more fine grained checks and ask the user what
    # they would like to do.
    _create_user_if_not_exists(user, password)
    _set_user_password(user, password)
    create_db_if_not_exists(db_name)
    grant_all_privileges_for_database(db_name, user)


def drop_db(db_name=None):
    if db_name is None:
        db_name = db_details['name']
    _mysql_exec_as_root('DROP DATABASE IF EXISTS %s' % db_name)


def dump_db(dump_filename='db_dump.sql', for_rsync=False):
    """Dump the database in the current working directory"""
    if not db_details['engine'].endswith('mysql'):
        raise InvalidArgumentError('dump_db only knows how to dump mysql so far')
    dump_cmd = ['mysqldump'] + _create_mysql_args()
    # this option will mean that there will be one line per insert
    # thus making the dump file better for rsync, but slightly bigger
    if for_rsync:
        dump_cmd.append('--skip-extended-insert')
    dump_cmd.append(db_details['name'])

    dump_file = open(dump_filename, 'w')
    if env['verbose']:
        print 'Executing dump command: %s\nSending stdout to %s' % (' '.join(dump_cmd), dump_filename)
    _call_command(dump_cmd, stdout=dump_file)
    dump_file.close()


def restore_db(dump_filename):
    """Restore a database dump file by name"""
    if not db_details['engine'].endswith('mysql'):
        raise InvalidProjectError('restore_db only knows how to restore mysql so far')

    restore_cmd = ['mysql'] + _create_mysql_args()

    dump_file = open(dump_filename, 'r')
    if env['verbose']:
        print 'Executing dump command: %s\nSending stdin to %s' % (' '.join(restore_cmd), dump_filename)
    _call_command(restore_cmd, stdin=dump_file)
    dump_file.close()


def setup_db_dumps(dump_dir):
    """ set up mysql database dumps in root crontab """
    if not path.isabs(dump_dir):
        raise InvalidArgumentError('dump_dir must be an absolute path, you gave %s' % dump_dir)
    project_name = env['django_dir'].split('/')[-1]
    cron_file = path.join('/etc', 'cron.daily', 'dump_' + project_name)

    if db_details['engine'].endswith('mysql'):
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
            f.write('/usr/bin/mysqldump ' + ' '.join(_create_mysql_args()))
            f.write(' > %s' % (db_details['name'], dump_file_stub))
            f.write(r'`/bin/date +\%d`.sql')
            f.write('\n')
        finally:
            f.close()

        os.chmod(cron_file, 0755)
