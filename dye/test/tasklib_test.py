import os, sys
import shutil
import unittest

dye_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(dye_dir)
import tasklib

example_dir = os.path.join(dye_dir, '..', 'examples', 'deploy')
sys.path.append(dye_dir)
import project_settings

tasklib.env['verbose'] = False
tasklib.env['quiet'] = False

class TestTaskLib(unittest.TestCase):
    def setUp(self):
        self.testdir = os.path.join(os.path.dirname(__file__), 'testdir')
        project_settings.project_name = 'testproj'
        project_settings.django_apps = ['testapp',]
        project_settings.django_relative_dir   = ("django/" +
                project_settings.project_name)
        tasklib._setup_paths(project_settings, None)
        tasklib.env['deploy_dir']   = os.path.dirname(__file__)
        tasklib.env['project_dir']  = self.testdir
        tasklib.env['django_dir']   = os.path.join(tasklib.env['project_dir'],
                project_settings.django_relative_dir)
        tasklib.env['ve_dir']       = os.path.join(tasklib.env['django_dir'], '.ve')
        tasklib.env['python_bin']   = os.path.join(tasklib.env['ve_dir'], 'bin', 'python2.6')
        tasklib.env['manage_py']    = os.path.join(tasklib.env['django_dir'], 'manage.py')
        # set up directories
        if not os.path.exists(tasklib.env['django_dir']):
            os.makedirs(tasklib.env['django_dir'])

    def tearDown(self):
        shutil.rmtree(self.testdir)

    def test_link_local_settings_exits_if_settings_py_not_present(self):
        """ We don't create settings.py, just call link_local_settings()
        and see if it dies with the correct error """
        self.assertRaises(tasklib.link_local_settings('dev'),
                SystemExit)


    def test_link_local_settings(self):
        local_settings_path = os.path.join(tasklib.env['django_dir'], 'local_settings.py')
        local_settings_dev_path = local_settings_path + '.dev'
        # create local_settings.py.dev, run link_local_settings, confirm it exists
        lsdev = open(local_settings_dev_path, 'w')
        lsdev.write('# python file')
        lsdev.close()
        tasklib.link_local_settings('dev')
        self.assertTrue(os.path.islink(local_settings_path))

if __name__ == '__main__':
    unittest.main()
