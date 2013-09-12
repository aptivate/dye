import os
from os import path
import sys
import unittest

# make sure a project_settings is available
dye_dir = path.join(path.dirname(__file__), os.pardir)
sys.path.append(dye_dir)
example_dir = path.join(dye_dir, os.pardir, '{{cookiecutter.repo_name}}', 'deploy')
sys.path.append(example_dir)

# import from dye
import tasks


class TasksMainTests(unittest.TestCase):

    def test_main_h_exits_with_0(self):
        exit_code = tasks.main(['-h'])
        self.assertEqual(0, exit_code)


class TasksArgumentConversionTests(unittest.TestCase):

    def test_convert_argument_converts_true_to_boolean_true(self):
        result = tasks.convert_argument('true')
        self.assertEqual(True, result)

    def test_convert_argument_converts_false_to_boolean_false(self):
        result = tasks.convert_argument('false')
        self.assertEqual(False, result)

    def test_convert_argument_converts_numeric_test_to_number(self):
        result = tasks.convert_argument('15')
        self.assertEqual(15, result)

    def test_convert_argument_leaves_other_text_as_text(self):
        result = tasks.convert_argument('sometext')
        self.assertEqual('sometext', result)

    def test_convert_task_bits_deals_with_lone_function(self):
        func, pos_args, kwargs = tasks.convert_task_bits('func')
        self.assertEqual('func', func)
        self.assertSequenceEqual((), pos_args)
        self.assertDictEqual({}, kwargs)

    def test_convert_task_bits_deals_with_function_and_one_pos_arg(self):
        func, pos_args, kwargs = tasks.convert_task_bits('func:arg1')
        self.assertEqual('func', func)
        self.assertSequenceEqual(('arg1',), pos_args)
        self.assertDictEqual({}, kwargs)

    def test_convert_task_bits_deals_with_function_and_multiple_pos_args(self):
        func, pos_args, kwargs = tasks.convert_task_bits('func:arg1,arg2')
        self.assertEqual('func', func)
        self.assertSequenceEqual(('arg1', 'arg2'), pos_args)
        self.assertDictEqual({}, kwargs)

    def test_convert_task_bits_deals_with_function_and_one_kw_arg(self):
        func, pos_args, kwargs = tasks.convert_task_bits('func:kw1=arg1')
        self.assertEqual('func', func)
        self.assertSequenceEqual((), pos_args)
        self.assertDictEqual({'kw1': 'arg1'}, kwargs)

    def test_convert_task_bits_deals_with_function_and_multiple_kw_args(self):
        func, pos_args, kwargs = tasks.convert_task_bits('func:kw1=arg1,kw2=arg2')
        self.assertEqual('func', func)
        self.assertSequenceEqual((), pos_args)
        self.assertDictEqual({'kw1': 'arg1', 'kw2': 'arg2'}, kwargs)

    def test_convert_task_bits_deals_with_both_pos_args_and_kw_args(self):
        func, pos_args, kwargs = tasks.convert_task_bits('func:arg,kw=arg')
        self.assertEqual('func', func)
        self.assertSequenceEqual(('arg',), pos_args)
        self.assertDictEqual({'kw': 'arg'}, kwargs)


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
