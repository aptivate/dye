import os
from os import path
import sys
import unittest

dye_dir = path.join(path.dirname(__file__), os.pardir)
sys.path.append(dye_dir)
import tasklib

from tasklib import database

tasklib.env['verbose'] = False
tasklib.env['quiet'] = True

# cache this in a global variable so that we only need it once
mysql_root_password = None


class MysqlMixin(object):

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
        database._mysql_exec_as_root("CREATE USER 'dye_user'@'localhost' IDENTIFIED BY 'dye_password'")

    def drop_database_user(self):
        self.get_mysql_root_password()
        database._mysql_exec_as_root("DROP USER 'dye_user'@'localhost'")

    def create_database(self):
        self.get_mysql_root_password()
        database._mysql_exec_as_root("CREATE DATABASE dyedb CHARACTER SET utf8")

    def grant_privileges(self):
        self.get_mysql_root_password()
        database._mysql_exec_as_root("GRANT ALL PRIVILEGES ON dyedb.* TO 'dye_user'@'localhost'")
        database._mysql_exec_as_root("FLUSH PRIVILEGES")

    def drop_database(self):
        self.get_mysql_root_password()
        database._mysql_exec_as_root("DROP DATABASE dyedb")


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

    # database tests?!? as root and as user

    # db exists

    # db table exists

    # create test db

    # dump db

    # restore db


if __name__ == '__main__':
    unittest.main()
