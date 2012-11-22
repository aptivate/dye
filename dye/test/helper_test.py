import os, sys
import unittest

dye_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(dye_dir)
import helper

class TestHelper(unittest.TestCase):
    def test_item_added_if_not_present(self):
        testdict = {'a': 'b'}
        helper.set_dict_if_not_set(testdict, 'b', 'c')
        self.assertEqual('c', testdict['b'])

    def test_item_not_added_if_present(self):
        testdict = {'a': 'b'}
        helper.set_dict_if_not_set(testdict, 'a', 'c')
        self.assertEqual('b', testdict['a'])

if __name__ == '__main__':
    unittest.main()
