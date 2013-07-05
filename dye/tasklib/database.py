import os
from os import path
import getpass

from .exceptions import InvalidArgumentError, InvalidProjectError
from .util import (_check_call_wrapper, _call_wrapper, _capture_command,
        _call_command, _create_dir_if_not_exists, CalledProcessError)

# this is a global dictionary
from .environment import env

# make sure WindowsError is available
import __builtin__
if not hasattr(__builtin__, 'WindowsError'):
    from .util import WindowsError

# a global dictionary for database details
db_details = {
    'engine': None,
    'name': None,
    'user': None,
    'password': None,
    'port': None,
    'host': None,
    'root_password': None,
    'grant_enabled': True,   # might want to disable the below sometimes
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
        root_pw = None
        # first try and get password from file
        root_pw_file = '/root/mysql_root_password'
        try:
            # we use this rather than file exists so that the script doesn't
            # have to be run as root
            file_exists = _call_wrapper(['sudo', 'test', '-f', root_pw_file])
        except (WindowsError, CalledProcessError):
            file_exists = 1
        if file_exists == 0:
            # note this requires sudoers to work with this - jenkins particularly ...
            root_pw = _capture_command(["sudo", "cat", root_pw_file])
            root_pw = root_pw.rstrip()
            # maybe it is wrong (on developer machine) - check it
            if not _test_mysql_root_password(root_pw):
                if env['verbose']:
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
        db_details['root_password'] = root_pw

    return db_details['root_password']


def _create_mysql_args(db_name=None, as_root=False, root_password=None):
    db_details = _get_db_details()
    # the password is pass
    if as_root:
        user = 'root'
        # do this so that _test_mysql_root_password() can run without
        # getting stuck in a loop.  It is called by _get_mysql_root_password()
        # so we don't want to call it again ...
        if root_password:
            password = root_password
        else:
            password = _get_mysql_root_password()
    else:
        user = db_details['user']
        password = db_details['password']
    if db_name is None:
        db_name = db_details['name']

    mysql_args = [
        '-u', user,
        '-p%s' % password,
        '--host=%s' % db_details['host'],
    ]
    if db_details['port'] is not None:
        mysql_args.append('--port=%s' % db_details['port'])
    if not as_root:
        mysql_args.append(db_name)
    return mysql_args


def _mysql_exec(mysql_cmd, db_name=None, capture_output=False, as_root=False, root_password=None):
    """execute a SQL statement using the mysql command line client.
    We do this rather than using the python libraries so this script can be
    run without the python libraries being installed.  (Also this was orginally
    written for fabric, so the code was already proven there)."""
    mysql_call = ['mysql'] + _create_mysql_args(db_name, as_root, root_password)
    mysql_call += ['-e', mysql_cmd]

    if capture_output:
        return _capture_command(mysql_call)
    else:
        _check_call_wrapper(mysql_call)


def _mysql_exec_as_root(mysql_cmd, root_password=None):
    """ execute a SQL statement using MySQL as the root MySQL user"""
    _mysql_exec(mysql_cmd, as_root=True, root_password=root_password)


def _test_mysql_root_password(password):
    """Try a no-op with the root password"""
    try:
        _mysql_exec_as_root('select 1', password)
    except CalledProcessError:
        return False
    return True


def db_exists(db_name):
    try:
        _mysql_exec('quit', db_name)
        return True
    except CalledProcessError:
        return False


def db_table_exists(table_name):
    tables = _mysql_exec('show tables', capture_output=True)
    table_list = tables.split()
    return table_name in table_list


def create_db_if_not_exists(db_name=None, drop_after_create=False):
    db_details = _get_db_details()
    if db_name is None:
        db_name = db_details['name']

    if not db_exists(db_name):
        _mysql_exec_as_root('CREATE DATABASE %s CHARACTER SET utf8' % db_name)
        if db_details['grant_enabled']:
            _mysql_exec_as_root('GRANT ALL PRIVILEGES ON %s.* TO \'%s\'@\'localhost\' IDENTIFIED BY \'%s\'' %
                (db_name, db_details['user'], db_details['password']))
        if drop_after_create:
            _mysql_exec_as_root(('DROP DATABASE %s' % db_name))


def drop_db(db_name=None):
    db_details = _get_db_details()
    if db_name is None:
        db_name = db_details['name']
    _mysql_exec_as_root('DROP DATABASE IF EXISTS %s' % db_name)


def dump_db(dump_filename='db_dump.sql', for_rsync=False):
    """Dump the database in the current working directory"""
    db_details = _get_db_details()
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
    db_details = _get_db_details()
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

    db_details = _get_db_details()
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
