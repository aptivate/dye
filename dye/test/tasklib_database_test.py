import os
from os import path
import sys
import StringIO
import unittest
import sqlite3
import MySQLdb

dye_dir = path.join(path.dirname(__file__), os.pardir)
sys.path.append(dye_dir)
import tasklib

from tasklib import database

tasklib.env['verbose'] = False
tasklib.env['quiet'] = True

# cache this in a global variable so that we only need it once
mysql_root_password = None


class TestSqliteManager(unittest.TestCase):
    TEST_DB = 'dyedb'
    TEST_TABLE = 'dyetable'

    def setUp(self):
        self.db = database.get_db_manager(
            engine='sqlite',
            name=self.TEST_DB,
            root_dir='.',
        )
        super(TestSqliteManager, self).setUp()

    def tearDown(self):
        self.db.drop_db()

    def create_db(self):
        conn = sqlite3.connect(self.db.file_path)
        conn.close()
        # check this has done what we expect
        self.assertTrue(path.exists(self.db.file_path))

    def create_table(self):
        conn = sqlite3.connect(self.db.file_path)
        conn.execute("CREATE TABLE %s (mycolumn CHAR(30))" % self.TEST_TABLE)

    def test_drop_db_deletes_db_file(self):
        self.create_db()
        self.db.drop_db()
        self.assertFalse(path.exists(self.db.file_path))

    def test_drop_db_doesnt_give_error_when_db_doesnt_exist(self):
        # check our assumptions are correct
        self.assertFalse(path.exists(self.db.file_path))
        try:
            self.db.drop_db()
        except Exception as e:
            self.fail(
                'Exception %s thrown by sqlite drop_db() when no db file present'
                % e)

    def test_test_db_table_exists_returns_false_when_table_not_present(self):
        self.create_db()
        self.assertFalse(self.db.test_db_table_exists('testtable'))

    def test_test_db_table_exists_returns_false_when_table_present(self):
        self.create_db()
        self.create_table()
        self.assertTrue(self.db.test_db_table_exists(self.TEST_TABLE))


class MysqlMixin(object):

    TEST_USER = 'dye_user'
    TEST_PASSWORD = 'dye_password'
    TEST_DB = 'dyedb'
    TEST_TABLE = 'dyetable'

    def setUp(self):
        self.db = database.get_db_manager(
            engine='mysql',
            name=self.TEST_DB,
            user=self.TEST_USER,
            password=self.TEST_PASSWORD,
            port=None,
            host=None,
            root_password=None,
            grant_enabled=True,
        )
        super(MysqlMixin, self).setUp()

    def get_mysql_root_password(self):
        """Use the global mysql_root_password as a cache, so we only need to
        don't need to keep asking the user for it.  Bit of a hack, but making it
        less hacky bit by bit.
        """
        global mysql_root_password
        if mysql_root_password is None:
            # this caches the root password in a global in database
            mysql_root_password = self.db.get_root_password()
        else:
            # if we've saved it, poke it into the database global
            # then it can be used without us having to pass it in ourselves
            self.db.root_password = mysql_root_password
        return mysql_root_password

    def drop_database_user(self):
        self.get_mysql_root_password()
        if self.db.test_sql_user_exists():
            self.db.exec_as_root("DROP USER '%s'@'localhost'" % self.TEST_USER)

    def create_database_user(self):
        self.get_mysql_root_password()
        self.drop_database_user()
        self.db.exec_as_root(
            "CREATE USER '%s'@'localhost' IDENTIFIED BY '%s'" %
            (self.TEST_USER, self.TEST_PASSWORD))

    def drop_database(self):
        self.get_mysql_root_password()
        if self.db.db_exists():
            self.db.exec_as_root("DROP DATABASE %s" % self.TEST_DB)

    def create_database(self):
        self.get_mysql_root_password()
        self.drop_database()
        self.db.exec_as_root("CREATE DATABASE %s CHARACTER SET utf8" % self.TEST_DB)

    def create_table(self):
        self.get_mysql_root_password()
        self.db.exec_as_root("CREATE TABLE %s.%s(mycolumn CHAR(30))" %
                             (self.TEST_DB, self.TEST_TABLE))

    def grant_privileges(self):
        self.get_mysql_root_password()
        self.db.exec_as_root(
            "GRANT ALL PRIVILEGES ON %s.* TO '%s'@'localhost'" %
            (self.TEST_DB, self.TEST_USER))
        self.db.exec_as_root("FLUSH PRIVILEGES")

    def assert_user_has_access_to_database(self):
        try:
            db_conn = self.db.create_db_connection()
        except MySQLdb.OperationalError as e:
            self.fail("Failed to connect to database after privileges "
                      "should have been granted.\n%s" % e)
        db_conn.close()


class TestCreateMysqlArgs(MysqlMixin, unittest.TestCase):

    def test_create_cmdline_args_simple_case(self):
        sql_args = self.db.create_cmdline_args()
        expected_args = ['-u', 'dye_user', '-pdye_password', '--host=localhost', 'dyedb']
        self.assertSequenceEqual(expected_args, sql_args)

    def test_create_cmdline_args_with_host(self):
        self.db.host = 'dbserver.com'
        sql_args = self.db.create_cmdline_args()
        expected_args = ['-u', 'dye_user', '-pdye_password', '--host=dbserver.com', 'dyedb']
        self.assertSequenceEqual(expected_args, sql_args)

    def test_create_cmdline_args_with_port(self):
        self.db.port = 3333
        sql_args = self.db.create_cmdline_args()
        expected_args = ['-u', 'dye_user', '-pdye_password', '--host=localhost', '--port=3333', 'dyedb']
        self.assertSequenceEqual(expected_args, sql_args)

    def test_create_cmdline_args_with_setting_database_name(self):
        self.db.name = 'mydb'
        sql_args = self.db.create_cmdline_args()
        expected_args = ['-u', 'dye_user', '-pdye_password', '--host=localhost', 'mydb']
        self.assertSequenceEqual(expected_args, sql_args)


class TestDatabaseTestFunctions(MysqlMixin, unittest.TestCase):

    def test_test_sql_user_exists_return_false_when_user_doesnt_exist(self):
        self.assertFalse(self.db.test_sql_user_exists())

    def test_test_sql_user_exists_return_true_when_user_does_exist(self):
        self.create_database_user()
        try:
            self.assertTrue(self.db.test_sql_user_exists())
        finally:
            self.drop_database_user()

    def test_test_sql_user_password_returns_false_when_user_doesnt_exist(self):
        self.assertFalse(self.db.test_sql_user_password())

    def test_test_sql_user_password_returns_false_when_user_exists_but_password_wrong(self):
        self.create_database_user()
        try:
            self.assertFalse(self.db.test_sql_user_password(
                user=self.TEST_USER, password='wrong_password'))
        finally:
            self.drop_database_user()

    def test_test_sql_user_password_returns_true_when_user_exists(self):
        self.create_database_user()
        try:
            self.assertTrue(self.db.test_sql_user_password())
        finally:
            self.drop_database_user()

    def test_test_root_password_returns_true_when_password_works(self):
        password = self.get_mysql_root_password()
        self.assertTrue(self.db.test_root_password(password))

    def test_test_root_password_returns_false_when_password_is_wrong(self):
        self.assertFalse(self.db.test_root_password('wrong_password'))

    def test_db_exists_returns_false_when_database_doesnt_exist(self):
        self.assertFalse(self.db.db_exists())

    def test_db_exists_returns_true_when_database_exists(self):
        self.create_database()
        try:
            self.assertTrue(self.db.db_exists())
        finally:
            self.drop_database()

    def test_test_db_table_exists_returns_true_when_table_exists(self):
        self.create_database_user()
        self.create_database()
        self.grant_privileges()
        self.create_table()
        try:
            self.assertTrue(self.db.test_db_table_exists(self.TEST_TABLE))
        finally:
            self.drop_database()
            self.drop_database_user()

    def test_test_db_table_exists_returns_false_when_table_doesnt_exist(self):
        self.create_database_user()
        self.create_database()
        self.grant_privileges()
        try:
            self.assertFalse(self.db.test_db_table_exists(self.TEST_TABLE))
        finally:
            self.drop_database()
            self.drop_database_user()


class TestDatabaseCreateFunctions(MysqlMixin, unittest.TestCase):

    def test_create_user_if_not_exists_creates_user_if_user_doesnt_exist(self):
        try:
            self.db.create_user_if_not_exists()
            self.assertTrue(self.db.test_sql_user_exists())
        finally:
            self.drop_database_user()

    def test_create_user_if_not_exists_doesnt_raise_exception_if_user_exists(self):
        self.create_database_user()
        try:
            self.db.create_user_if_not_exists()
            self.assertTrue(self.db.test_sql_user_exists())
        finally:
            self.drop_database_user()

    def test_set_user_password_changes_user_password(self):
        self.create_database_user()
        try:
            self.db.password = 'new_password'
            self.db.set_user_password()
            self.assertTrue(self.db.test_sql_user_password(
                password='new_password'))
        finally:
            self.drop_database_user()

    def test_grant_all_privileges_for_database_gives_access_to_db(self):
        self.create_database_user()
        self.create_database()
        try:
            self.db.grant_all_privileges_for_database()
            self.assert_user_has_access_to_database()
        finally:
            self.drop_database()
            self.drop_database_user()

    def test_create_db_if_not_exists_creates_db_when_db_does_not_exist(self):
        self.db.create_db_if_not_exists()
        try:
            self.assertTrue(self.db.db_exists())
        finally:
            self.drop_database()

    def test_create_db_if_not_exists_creates_db_does_not_cause_error_when_db_does_exist(self):
        self.create_database()
        try:
            self.db.create_db_if_not_exists()
        except Exception as e:
            self.fail('create_db_if_not_exists() raised exception: %s' % e)
        finally:
            self.drop_database()

    def test_ensure_user_and_db_exist_creates_user_and_db_when_they_dont_exist(self):
        try:
            self.db.ensure_user_and_db_exist()
            self.assert_user_has_access_to_database()
        finally:
            self.drop_database_user()
            self.drop_database()

    def test_ensure_user_and_db_exist_doesnt_cause_error_when_user_and_db_exist(self):
        self.create_database_user()
        self.create_database()
        self.grant_privileges()
        try:
            self.db.ensure_user_and_db_exist()
        except Exception as e:
            self.fail('ensure_user_and_db_exist() raised exception: %s' % e)
        finally:
            self.drop_database_user()
            self.drop_database()

    def test_drop_db_does_drop_database(self):
        self.create_database()
        self.db.drop_db()
        self.assertFalse(self.db.db_exists())

    def test_drop_db_doesnt_cause_error_when_db_doesnt_exist(self):
        try:
            self.db.drop_db()
        except Exception as e:
            self.fail('drop_db() raised exception: %s' % e)

    # dump db
    # do a restore from a saved test dump file
    # do the dump
    # check the generated dump file matches test dump (but think about time
    # stamps ...)

    # restore db
    # ensure db does not exist
    # do restore
    # check db and table exist


class TestMysqlDumpCron(MysqlMixin, unittest.TestCase):

    def test_create_dbdump_cron_file_writes_correct_output(self):
        dump_file_stub = '/var/dumps/dye-'
        output_file = StringIO.StringIO()
        self.db.create_dbdump_cron_file(output_file, dump_file_stub)
        actual_output = output_file.getvalue()
        expected_output = \
            "#!/bin/sh\n" \
            "/usr/bin/mysqldump -u dye_user -pdye_password " \
            "--host=localhost dyedb > /var/dumps/dye-`/bin/date +\%d`.sql\n"
        self.assertEqual(expected_output, actual_output)


if __name__ == '__main__':
    unittest.main()
