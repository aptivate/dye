import os
from os import path
import sys
import unittest

# make sure a project_settings is available
dye_dir = path.join(path.dirname(__file__), os.pardir)
sys.path.append(dye_dir)
example_dir = path.join(dye_dir, os.pardir, 'examples', 'deploy')
sys.path.append(example_dir)

# import from dye
import tasks


class TasksMainTests(unittest.TestCase):

    def test_main_h_exits_with_0(self):
        exit_code = tasks.main(['-h'])
        self.assertEqual(0, exit_code)


class TasksGetPublicCallablesTests(unittest.TestCase):

    def test_get_public_callables_returns_public_functions(self):
        from testdeploy import empty_module as test_module

        def public_function():
            pass

        test_module.public_function = public_function

        public_callables = tasks.get_public_callables(test_module)
        self.assertEqual(['public_function'], public_callables)

    def test_get_public_callables_does_not_return_private_functions(self):
        from testdeploy import empty_module as test_module

        def private_function():
            pass

        test_module._private_function = private_function

        public_callables = tasks.get_public_callables(test_module)
        self.assertEqual([], public_callables)

    def test_get_public_callables_does_not_return_classes(self):
        from testdeploy import empty_module as test_module

        class a_class(object):
            def a_method(self):
                pass

        test_module.a_class = a_class
        public_callables = tasks.get_public_callables(test_module)
        self.assertEqual([], public_callables)

    def test_get_public_callables_does_not_return_variables(self):
        from testdeploy import empty_module as test_module
        test_module.a_string = "a string"
        public_callables = tasks.get_public_callables(test_module)
        self.assertEqual([], public_callables)

    def test_get_public_callables_returns_empty_list_when_passed_none(self):
        public_callables = tasks.get_public_callables(None)
        self.assertEqual([], public_callables)
