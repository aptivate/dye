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


class TestCreateMysqlArgs(unittest.TestCase):

    def setUp(self):
        database.db_details = {
            'engine': 'mysql',
            'name': 'dyedb',
            'user': 'dye_user',
            'password': 'dye_password',
            'port': None,
            'host': None,
            'root_password': 'root_pw',
            'grant_enabled': True,   # might want to disable the below sometimes
        }

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

    def test_create_mysql_args_with_root_user(self):
        mysql_args = database._create_mysql_args(as_root=True)
        expected_args = ['-u', 'root', '-proot_pw']
        self.assertSequenceEqual(expected_args, mysql_args)

    def test_create_mysql_args_with_root_user_and_setting_root_password(self):
        mysql_args = database._create_mysql_args(as_root=True, root_password='s3cr3t')
        expected_args = ['-u', 'root', '-ps3cr3t']
        self.assertSequenceEqual(expected_args, mysql_args)

    # database tests?!? as root and as user

    # db exists

    # db table exists

    # create test db

    # dump db

    # restore db


if __name__ == '__main__':
    unittest.main()
