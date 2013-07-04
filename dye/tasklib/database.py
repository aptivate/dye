import getpass

from .util import (_check_call_wrapper, _call_wrapper, _capture_command,
        CalledProcessError)

# this is a global dictionary
from .environment import env

# make sure WindowsError is available
import __builtin__
if not hasattr(__builtin__, 'WindowsError'):
    from .util import WindowsError


def _get_mysql_root_password():
    # first try to read the root password from a file
    # otherwise ask the user
    if 'root_pw' not in env:
        root_pw = None
        # first try and get password from file
        root_pw_file = '/root/mysql_root_password'
        try:
            file_exists = _call_wrapper(['sudo', 'test', '-f', root_pw_file])
        except (WindowsError, CalledProcessError):
            file_exists = 1
        if file_exists == 0:
            # note this requires sudoers to work with this - jenkins particularly ...
            root_pw = _capture_command(["sudo", "cat", root_pw_file])
            root_pw = root_pw.rstrip()
            # maybe it is wrong (on developer machine) - check it
            if not _test_mysql_root_password(root_pw):
                if not env['verbose']:
                    print "mysql root password in %s doesn't work" % root_pw_file
                root_pw = None

        # still haven't got it, ask the user
        while not root_pw:
            print "about to ask user for password"
            root_pw = getpass.getpass('Enter MySQL root password:')
            if not _test_mysql_root_password(root_pw):
                if not env['quiet']:
                    print "Sorry, invalid password"
                root_pw = None

        # now we have root password that works
        env['root_pw'] = root_pw

    return env['root_pw']


def _mysql_exec_as_root(mysql_cmd, root_password=None):
    """ execute a SQL statement using MySQL as the root MySQL user"""
    # do this so that _test_mysql_root_password() can run without
    # getting stuck in a loop
    if not root_password:
        root_password = _get_mysql_root_password()
    mysql_call = ['mysql', '-u', 'root', '-p%s' % root_password]
    mysql_call += ['--host=%s' % env['db_host']]

    if env['db_port'] is not None:
        mysql_call += ['--port=%s' % env['db_port']]
    mysql_call += ['-e']
    _check_call_wrapper(mysql_call + [mysql_cmd])


def _test_mysql_root_password(password):
    """Try a no-op with the root password"""
    try:
        _mysql_exec_as_root('select 1', password)
    except CalledProcessError:
        return False
    return True


def db_exists(db_user, db_pw, db_name, db_port, db_host):
    db_exist_call = ['mysql', '-u', db_user, '-p%s' % db_pw]
    db_exist_call += ['--host=%s' % db_host]

    if db_port is not None:
        db_exist_call += ['--port=%s' % db_port]

    db_exist_call += [db_name, '-e', 'quit']
    try:
        _check_call_wrapper(db_exist_call)
        return True
    except CalledProcessError:
        return False


def db_table_exists(table_name, db_user, db_pw, db_name, db_port, db_host):
    table_list_call = ['mysql', '-u', db_user, '-p%s' % db_pw]
    table_list_call += ['--host=%s' % db_host]

    if db_port is not None:
        table_list_call += ['--port=%s' % db_port]

    table_list_call += [db_name, '-e', 'show tables']
    tables = _capture_command(table_list_call)
    table_list = tables.split()
    return table_name in table_list
