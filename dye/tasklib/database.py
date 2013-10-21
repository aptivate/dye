import os
from os import path
import sqlite3
import MySQLdb

from .exceptions import InvalidArgumentError, InvalidProjectError
from .util import (_check_call_wrapper, _capture_command,
                   _call_command, _create_dir_if_not_exists,
                   CalledProcessError, _ask_for_password, _get_file_contents)

# this is a global dictionary
from .environment import env


# the methods in this class are those used externally
class DBManager(object):

    # the first four are required for tasks.py deploy
    def drop_db(self):
        raise NotImplementedError()

    def ensure_user_and_db_exist(self):
        raise NotImplementedError()

    def test_db_table_exists(self, table):
        raise NotImplementedError()

    # this is used directly for the test database
    def grant_all_privileges_for_database(self):
        raise NotImplementedError()

    # these four are only required for fablib deploy, which is why I
    # haven't implemented them for sqlite
    def dump_db(self, dump_filename='db_dump.sql', for_rsync=False):
        raise NotImplementedError()

    def restore_db(self, dump_filename):
        raise NotImplementedError()

    def create_dbdump_cron_file(self, cron_file, dump_file_stub):
        raise NotImplementedError()

    def setup_db_dumps(self, dump_dir):
        raise NotImplementedError()


class SqliteManager(DBManager):

    ENGINE = 'Sqlite'

    def __init__(self, name, root_dir):
        if path.isabs(name):
            self.file_path = name
        else:
            self.file_path = path.abspath(path.join(root_dir, name))

    def drop_db(self):
        if path.exists(self.file_path):
            os.remove(self.file_path)

    # django syncdb will create the sqlite table
    def ensure_user_and_db_exist(self):
        pass

    def test_db_table_exists(self, table):
        conn = sqlite3.connect(self.file_path)
        try:
            result = conn.execute(
                "select name from sqlite_master where type = 'table' and "
                "name = '%s'" % table)
            return len(list(result.fetchall())) != 0
        finally:
            conn.close()

    # this is used directly for the test database
    def grant_all_privileges_for_database(self):
        # no privileges in sqlite world
        pass


class MySQLManager(DBManager):

    ENGINE = 'MySQL'
    root_pw_file = '/root/mysql_root_password'
    root_pw_file_needs_sudo = True

    def __init__(self, name, user, password, port=None, host=None,
                 root_password=None, grant_enabled=True):
        self.name = name
        self.user = user
        self.password = password
        self.port = int(port) if port else None
        if not host:
            self.host = 'localhost'
        else:
            self.host = host
        self.root_password = root_password
        self.grant_enabled = grant_enabled
        # connections to the database for the normal user and the root
        # user
        self.user_db_conn = None
        self.root_db_conn = None

    def get_root_password(self):
        """This can be overridden (by monkeypatching) if required."""
        # first try to read the root password from a file
        # otherwise ask the user
        if self.root_password is None:
            root_pw = _get_file_contents(self.root_pw_file, sudo=self.root_pw_file_needs_sudo)
            # maybe it is wrong (on developer machine) - check it
            if root_pw is not None and not self.test_root_password(root_pw):
                if env['verbose']:
                    print "mysql root password in %s doesn't work" % self.root_pw_file
                root_pw = None

            # still haven't got it, ask the user
            if root_pw is None and not env['quiet']:
                root_pw = _ask_for_password("", test_fn=self.test_root_password)

            # now we have root password that works
            self.root_password = root_pw

        return self.root_password

    def test_sql_user_password(self, user=None, password=None):
        # try to connect
        kwargs = {
            'user': user if user else self.user,
            'passwd': password if password else self.password,
        }
        try:
            db_conn = self.create_db_connection(**kwargs)
        except MySQLdb.OperationalError as e:
            if e.args[0] == 1045:  # access denied for user/password
                return False
            else:
                raise e
        db_conn.close()
        return True

    def test_root_password(self, password):
        """Try a no-op with the root password"""
        return self.test_sql_user_password(user='root', password=password)

    def create_db_connection(self, **kwargs):
        if self.host:
            kwargs.setdefault('host', self.host)
        if self.port:
            kwargs.setdefault('port', self.port)
        return MySQLdb.connect(**kwargs)

    def get_user_db_cursor(self, **cursor_kwargs):
        if self.user_db_conn is None:
            self.user_db_conn = self.create_db_connection(
                user=self.user,
                passwd=self.password,
                db=self.name
            )
        return self.user_db_conn.cursor(**cursor_kwargs)

    def close_user_db_connection(self):
        if self.user_db_conn is not None:
            self.user_db_conn.close()
            self.user_db_conn = None

    def get_root_db_cursor(self, **cursor_kwargs):
        if self.root_db_conn is None:
            self.root_db_conn = self.create_db_connection(
                user='root',
                passwd=self.get_root_password()
            )
        return self.root_db_conn.cursor(**cursor_kwargs)

    def close_root_db_connection(self):
        if self.root_db_conn is not None:
            self.root_db_conn.close()
            self.root_db_conn = None

    def create_cmdline_args(self):
        cmdline_args = [
            '-u', self.user,
            '-p%s' % self.password,
        ]
        if self.host:
            cmdline_args.append('--host=%s' % self.host)
        if self.port:
            cmdline_args.append('--port=%s' % self.port)
        cmdline_args.append(self.name)
        return cmdline_args

    def sql_exec(self, sql_cmd, db_name=None, capture_output=False):
        """execute a SQL statement using the mysql command line client.
        We do this rather than using the python libraries so this script can
        be run without the python libraries being installed.  (Also this was
        orginally written for fabric, so the code was already proven there)."""
        cmdline_call = ['mysql'] + self.create_cmdline_args(db_name)
        cmdline_call += ['-e', sql_cmd]

        if capture_output:
            return _capture_command(cmdline_call)
        else:
            _check_call_wrapper(cmdline_call)

    def exec_as_root(self, *sql_cmd_list):
        """ execute a SQL statement using MySQL as the root MySQL user"""
        cursor = self.get_root_db_cursor()
        try:
            for cmd in sql_cmd_list:
                cursor.execute(cmd)
        finally:
            cursor.close()

    def test_sql_user_exists(self, user=None):
        # check user in mysql table
        if not user:
            user = self.user
        cursor = self.get_root_db_cursor()
        try:
            rows = cursor.execute(
                "SELECT 1 FROM mysql.user WHERE user = '%s'" % user)
        finally:
            cursor.close()
        return rows != 0

    def db_exists(self):
        cursor = self.get_root_db_cursor()
        try:
            cursor.execute("SHOW DATABASES")
            db_list = [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
        return self.name in db_list

    def test_db_table_exists(self, table_name):
        cursor = self.get_user_db_cursor()
        try:
            rows = cursor.execute("SHOW TABLES LIKE '%s'" % table_name)
        finally:
            cursor.close()
        return rows != 0

    def create_user_if_not_exists(self):
        if not self.grant_enabled:
            return
        if not self.test_sql_user_exists(self.user):
            self.exec_as_root(
                "CREATE USER '%s'@'%s' IDENTIFIED BY '%s'" %
                (self.user, self.host, self.password))

    def set_user_password(self):
        if not self.grant_enabled:
            return
        self.exec_as_root(
            "SET PASSWORD FOR '%s'@'%s' = PASSWORD('%s')" %
            (self.user, self.host, self.password))

    def grant_all_privileges_for_database(self):
        if not self.grant_enabled:
            return
        self.exec_as_root(
            "GRANT ALL PRIVILEGES ON %s.* TO '%s'@'%s'" % (self.name, self.user, self.host),
            "FLUSH PRIVILEGES",
        )

    def create_db_if_not_exists(self):
        if not self.db_exists():
            self.exec_as_root(
                'CREATE DATABASE %s CHARACTER SET utf8' % self.name)

    def ensure_user_and_db_exist(self):
        # the below just make sure things line up at the end of the process
        # TODO: should we do more fine grained checks and ask the user what
        # they would like to do.
        self.create_user_if_not_exists()
        self.set_user_password()
        self.create_db_if_not_exists()
        self.grant_all_privileges_for_database()

    def drop_db(self):
        self.exec_as_root('DROP DATABASE IF EXISTS %s' % self.name)

    def dump_db(self, dump_filename='db_dump.sql', for_rsync=False):
        """Dump the database in the current working directory"""
        dump_cmd = ['mysqldump'] + self.create_cmdline_args()
        # this option will mean that there will be one line per insert
        # thus making the dump file better for rsync, but slightly bigger
        if for_rsync:
            dump_cmd.append('--skip-extended-insert')

        with open(dump_filename, 'w') as dump_file:
            if env['verbose']:
                print 'Executing mysqldump command: %s\nSending stdout to %s' % \
                    (' '.join(dump_cmd), dump_filename)
            _call_command(dump_cmd, stdout=dump_file)
        dump_file.close()

    def restore_db(self, dump_filename):
        """Restore a database dump file by name"""
        restore_cmd = ['mysql'] + self.create_cmdline_args()
        with open(dump_filename, 'r') as dump_file:
            if env['verbose']:
                print 'Executing mysql restore command: %s\nSending stdin to %s' % \
                    (' '.join(restore_cmd), dump_filename)
            _call_command(restore_cmd, stdin=dump_file)

    def create_dbdump_cron_file(self, cron_file, dump_file_stub):
        # write something like:
        # #!/bin/sh
        # /usr/bin/mysqldump --user=projectname --password=aptivate --host=127.0.0.1 projectname >  /var/projectname/dumps/daily-dump-`/bin/date +\%d`.sql
        #
        # cron file should be an open file like object

        # don't use "with" for compatibility with python 2.3 on whov2hinari
        cron_file.write('#!/bin/sh\n')
        cron_file.write('/usr/bin/mysqldump ' +
                        ' '.join(self.create_cmdline_args()))
        cron_file.write(' > %s' % dump_file_stub)
        cron_file.write(r'`/bin/date +\%d`.sql')
        cron_file.write('\n')

    def setup_db_dumps(self, dump_dir):
        """ set up mysql database dumps in root crontab """
        if not path.isabs(dump_dir):
            raise InvalidArgumentError(
                'dump_dir must be an absolute path, you gave %s' % dump_dir)
        cron_file = path.join('/etc', 'cron.daily', 'dump_' + env['project_name'])

        _create_dir_if_not_exists(dump_dir)
        dump_file_stub = path.join(dump_dir, 'daily-dump-')

        # has it been set up already
        cron_set = True
        try:
            _check_call_wrapper(
                'sudo crontab -l | grep mysqldump | grep %s' % env['project_name'],
                shell=True)
        except CalledProcessError:
            cron_set = False

        if cron_set or path.exists(cron_file):
            return

        # don't use "with" for compatibility with python 2.3 on whov2hinari
        f = open(cron_file, 'w')
        try:
            self.create_dbdump_cron_file(f, dump_file_stub)
        finally:
            f.close()

        os.chmod(cron_file, 0755)


def get_db_manager(engine, **kwargs):
    if engine.lower() == 'mysql':
        return MySQLManager(**kwargs)
    elif engine.lower() in ['sqlite', 'sqlite3']:
        return SqliteManager(**kwargs)
    else:
        raise InvalidProjectError('Database engine %s not supported' % engine)
