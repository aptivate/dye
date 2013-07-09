import os
from os import path
import sys
import unittest
import MySQLdb

dye_dir = path.join(path.dirname(__file__), os.pardir)
sys.path.append(dye_dir)
import tasklib

from tasklib import database

tasklib.env['verbose'] = False
tasklib.env['quiet'] = True

# cache this in a global variable so that we only need it once
mysql_root_password = None


class MysqlMixin(object):

    TEST_USER = 'dye_user'
    TEST_PASSWORD = 'dye_password'
    TEST_DB = 'dyedb'

    def set_default_db_details(self):
        database.db_details = {
            'engine': 'mysql',
            'name': 'dyedb',
            'user': 'dye_user',
            'password': 'dye_password',
            'port': None,
            'host': None,
            'root_password': 'root_pw',
            'grant_enabled': True,
        }

    def reset_db_details(self):
        database._reset_db_details()

    def get_mysql_root_password(self):
        """Use the global mysql_root_password as a cache, so we only need to
        don't need to keep asking the user for it.  Bit of a hack, but making it
        less hacky bit by bit.
        """
        global mysql_root_password
        if mysql_root_password is None:
            # this caches the root password in a global in database
            mysql_root_password = database._get_mysql_root_password()
        else:
            # if we've saved it, poke it into the database global
            # then it can be used without us having to pass it in ourselves
            database.db_details['root_password'] = mysql_root_password
        return mysql_root_password

    def create_database_user(self):
        self.get_mysql_root_password()
        database._mysql_exec_as_root(
            "CREATE USER '%s'@'localhost' IDENTIFIED BY '%s'" %
            (self.TEST_USER, self.TEST_PASSWORD))

    def drop_database_user(self):
        self.get_mysql_root_password()
        database._mysql_exec_as_root("DROP USER '%s'@'localhost'" % self.TEST_USER)

    def create_database(self):
        self.get_mysql_root_password()
        database._mysql_exec_as_root("CREATE DATABASE %s CHARACTER SET utf8" % self.TEST_DB)

    def grant_privileges(self):
        self.get_mysql_root_password()
        database._mysql_exec_as_root(
            "GRANT ALL PRIVILEGES ON %s.* TO '%s'@'localhost'" %
            (self.TEST_DB, self.TEST_USER))
        database._mysql_exec_as_root("FLUSH PRIVILEGES")

    def drop_database(self):
        self.get_mysql_root_password()
        database._mysql_exec_as_root("DROP DATABASE %s" % self.TEST_DB)

    def assert_user_has_access_to_database(self):
        try:
            db_conn = database._create_db_connection(
                user=self.TEST_USER,
                passwd=self.TEST_PASSWORD,
                db=self.TEST_DB,
            )
        except MySQLdb.OperationalError as e:
            self.fail("Failed to connect to database after privileges"
                      "should be granted.\n%s" % e)
        db_conn.close()


class TestCreateMysqlArgs(MysqlMixin, unittest.TestCase):

    def setUp(self):
        self.set_default_db_details()

    def tearDown(self):
        self.reset_db_details()

    def test_create_mysql_args_simple_case(self):
        mysql_args = database._create_mysql_args()
        expected_args = ['-u', 'dye_user', '-pdye_password', 'dyedb']
        self.assertSequenceEqual(expected_args, mysql_args)

    def test_create_mysql_args_with_host(self):
        database.db_details['host'] = 'dbserver.com'
        mysql_args = database._create_mysql_args()
        expected_args = ['-u', 'dye_user', '-pdye_password', '--host=dbserver.com', 'dyedb']
        self.assertSequenceEqual(expected_args, mysql_args)

    def test_create_mysql_args_with_port(self):
        database.db_details['port'] = 3333
        mysql_args = database._create_mysql_args()
        expected_args = ['-u', 'dye_user', '-pdye_password', '--port=3333', 'dyedb']
        self.assertSequenceEqual(expected_args, mysql_args)

    def test_create_mysql_args_with_setting_database_name(self):
        mysql_args = database._create_mysql_args(db_name='mydb')
        expected_args = ['-u', 'dye_user', '-pdye_password', 'mydb']
        self.assertSequenceEqual(expected_args, mysql_args)


class TestDatabaseTestFunctions(MysqlMixin, unittest.TestCase):

    def test_test_mysql_user_exists_return_false_when_user_doesnt_exist(self):
        self.assertFalse(database._test_mysql_user_exists(user=self.TEST_USER))

    def test_test_mysql_user_exists_return_true_when_user_does_exist(self):
        self.create_database_user()
        try:
            self.assertTrue(database._test_mysql_user_exists(user=self.TEST_USER))
        finally:
            self.drop_database_user()

    def test_test_mysql_user_password_works_returns_false_when_user_doesnt_exist(self):
        self.assertFalse(database._test_mysql_user_password_works(
            user=self.TEST_USER, password=self.TEST_PASSWORD))

    def test_test_mysql_user_password_works_returns_false_when_user_exists_but_password_wrong(self):
        self.create_database_user()
        try:
            self.assertFalse(database._test_mysql_user_password_works(
                user=self.TEST_USER, password='wrong_password'))
        finally:
            self.drop_database_user()

    def test_test_mysql_user_password_works_returns_true_when_user_exists(self):
        self.create_database_user()
        try:
            self.assertTrue(database._test_mysql_user_password_works(
                user=self.TEST_USER, password=self.TEST_PASSWORD))
        finally:
            self.drop_database_user()

    def test_test_mysql_root_password_returns_true_when_password_works(self):
        password = self.get_mysql_root_password()
        self.assertTrue(database._test_mysql_root_password(password))

    def test_test_mysql_root_password_returns_false_when_password_is_wrong(self):
        self.assertFalse(database._test_mysql_root_password('wrong_password'))

    def test_db_exists_returns_false_when_database_doesnt_exist(self):
        self.assertFalse(database._db_exists(self.TEST_DB))

    def test_db_exists_returns_true_when_database_exists(self):
        self.create_database()
        try:
            self.assertTrue(database._db_exists(self.TEST_DB))
        finally:
            self.drop_database()

    # TODO: db table exists


class TestDatabaseCreateFunctions(MysqlMixin, unittest.TestCase):

    def test_create_user_if_not_exists_creates_user_if_user_doesnt_exist(self):
        try:
            database._create_user_if_not_exists(user=self.TEST_USER, password=self.TEST_PASSWORD)
            self.assertTrue(database._test_mysql_user_exists(user=self.TEST_USER))
        finally:
            self.drop_database_user()

    def test_create_user_if_not_exists_doesnt_raise_exception_if_user_exists(self):
        self.create_database_user()
        try:
            database._create_user_if_not_exists(user=self.TEST_USER, password=self.TEST_PASSWORD)
            self.assertTrue(database._test_mysql_user_exists(user=self.TEST_USER))
        finally:
            self.drop_database_user()

    def test_set_user_password_changes_user_password(self):
        self.create_database_user()
        try:
            database._set_user_password(user=self.TEST_USER, password='new_password')
            self.assertTrue(database._test_mysql_user_password_works(
                user=self.TEST_USER, password='new_password'))
        finally:
            self.drop_database_user()

    def test_grant_all_privileges_for_database_gives_access_to_db(self):
        self.create_database_user()
        self.create_database()
        try:
            database.grant_all_privileges_for_database(
                db_name=self.TEST_DB, user=self.TEST_USER)
            self.assert_user_has_access_to_database()
        finally:
            self.drop_database()
            self.drop_database_user()

    def test_create_db_if_not_exists_creates_db_when_db_does_not_exist(self):
        database.create_db_if_not_exists(db_name=self.TEST_DB)
        try:
            self.assertTrue(database._db_exists(db_name=self.TEST_DB))
        finally:
            self.drop_database()

    def test_create_db_if_not_exists_creates_db_does_not_cause_error_when_db_does_exist(self):
        self.create_database()
        try:
            database.create_db_if_not_exists(db_name=self.TEST_DB)
        except Exception as e:
            self.fail('create_db_if_not_exists() raised exception: %s' % e)
        finally:
            self.drop_database()

    def test_ensure_user_and_db_exist_creates_user_and_db_when_they_dont_exist(self):
        try:
            database.ensure_user_and_db_exist(
                user=self.TEST_USER, password=self.TEST_PASSWORD,
                db_name=self.TEST_DB)
            self.assert_user_has_access_to_database()
        finally:
            self.drop_database_user()
            self.drop_database()

    def test_ensure_user_and_db_exist_doesnt_cause_error_when_user_and_db_exist(self):
        self.create_database_user()
        self.create_database()
        self.grant_privileges()
        try:
            database.ensure_user_and_db_exist(
                user=self.TEST_USER, password=self.TEST_PASSWORD,
                db_name=self.TEST_DB)
        except Exception as e:
            self.fail('ensure_user_and_db_exist() raised exception: %s' % e)
        finally:
            self.drop_database_user()
            self.drop_database()

    def test_drop_db_does_drop_database(self):
        self.create_database()
        database.drop_db(db_name=self.TEST_DB)
        self.assertFalse(database._db_exists(db_name=self.TEST_DB))

    def test_drop_db_doesnt_cause_error_when_db_doesnt_exist(self):
        try:
            database.drop_db(db_name=self.TEST_DB)
        except Exception as e:
            self.fail('drop_db() raised exception: %s' % e)

    # db table exists

    # dump db

    # restore db


if __name__ == '__main__':
    unittest.main()
