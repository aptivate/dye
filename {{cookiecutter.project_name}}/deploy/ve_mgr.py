from __future__ import unicode_literals, absolute_import
import os
import sys
import shutil
import subprocess
from os import path


def capture_command(argv):
    return subprocess.Popen(argv, stdout=subprocess.PIPE).communicate()[0]


def find_package_dir_in_ve(ve_dir, package):
    python = os.listdir(path.join(ve_dir, 'lib'))[0]
    site_dir = path.join(ve_dir, 'lib', python, 'site-packages')
    package_dir = path.join(site_dir, package)
    egglink = path.join(site_dir, package + '.egg-link')
    if path.isdir(package_dir):
        return package_dir
    elif path.isfile(egglink):
        return open(egglink, 'r').readline().strip()
    else:
        return None


def find_file(location_list):
    for file_location in location_list:
        if os.path.exists(file_location):
            return file_location
    return None


def find_python():
    """ work out which python to use """
    generic_python = os.path.join('/', 'usr', 'bin', 'python')
    python26 = generic_python + '2.6'
    python27 = generic_python + '2.7'
    paths_to_try = (python27, python26, generic_python, sys.executable)
    python_exe = find_file(paths_to_try)
    if not python_exe:
        raise Exception("Failed to find a valid Python executable " +
                "in any of these locations: %s" % paths_to_try)
    return python_exe


def check_python_version(min_python_major_version, min_python_minor_version, py_path):
    # check python version is high enough
    python_exe = 'python%d.%d' % (min_python_major_version, min_python_minor_version)

    if (sys.version_info[0] < min_python_major_version or
            sys.version_info[1] < min_python_minor_version):
        # we use the environ thing to stop recursing if unexpected things happen
        if 'RECALLED_CORRECT_PYTHON' not in os.environ:
            new_env = os.environ.copy()
            new_env['RECALLED_CORRECT_PYTHON'] = 'true'
            try:
                retcode = subprocess.call([python_exe, py_path] + sys.argv[1:],
                        env=new_env)
                sys.exit(retcode)
            except OSError:
                print >> sys.stderr, \
                    "You must use python %d.%d or later, you are using %d.%d" % (
                        min_python_major_version, min_python_minor_version,
                        sys.version_info[0], sys.version_info[1])
                print >> sys.stderr, "Could not find %s in path" % python_exe
                sys.exit(1)
        else:
            print >> sys.stderr, \
                "You must use python %d.%d or later, you are using %d.%d" % (
                    min_python_major_version, min_python_minor_version,
                    sys.version_info[0], sys.version_info[1])
            print >> sys.stderr, "Try doing '%s %s'" % (python_exe, sys.argv[0])
            sys.exit(1)


def in_virtualenv():
    """ Are we already in a virtualenv """
    return 'VIRTUAL_ENV' in os.environ or 'IN_VIRTUALENV' in os.environ


class UpdateVE(object):

    def __init__(self, ve_dir=None, requirements=None):

        if requirements:
            self.requirements = requirements
        else:
            try:
                from project_settings import local_requirements_file
            except ImportError:
                print >> sys.stderr, "could not find local_requirements_file in project_settings.py"
                raise
            self.requirements = local_requirements_file

        if ve_dir:
            self.ve_dir = ve_dir
        else:
            try:
                from project_settings import local_vcs_root, relative_ve_dir
                ve_dir = path.join(local_vcs_root, relative_ve_dir)
            except ImportError:
                print >> sys.stderr, "could not find local_vcs_root/relative_ve_dir in project_settings.py"
                raise
            self.ve_dir = ve_dir

        self.ve_timestamp = path.join(self.ve_dir, 'timestamp')

        import project_settings
        self.pypi_cache_url = getattr(project_settings, 'pypi_cache_url', None)
        # the major version must be exact, the minor version is a minimum
        self.python_version = getattr(project_settings, 'python_version', (2, 6))

    def update_ve_timestamp(self):
        os.utime(self.ve_dir, None)
        file(self.ve_timestamp, 'w').close()

    def check_virtualenv_python_version(self):
        """ returns True if the virtualenv python exists and is new enough """
        ve_python = path.join(self.ve_dir, 'bin', 'python')
        if not path.exists(ve_python):
            return False
        major_version = capture_command(
            [ve_python, '-c', 'import sys; print sys.version_info[0]'])
        if int(major_version) != self.python_version[0]:
            return False
        minor_version = capture_command(
            [ve_python, '-c', 'import sys; print sys.version_info[1]'])
        if int(minor_version) < self.python_version[1]:
            return False
        return True

    def check_current_python_version(self):
        if sys.version_info[0] != self.python_version[0]:
            return False
        if sys.version_info[1] != self.python_version[1]:
            return False
        return True

    def virtualenv_needs_update(self):
        """ returns True if the virtualenv needs an update """
        # timestamp of last modification of .ve/ directory
        ve_dir_mtime = path.exists(self.ve_dir) and path.getmtime(self.ve_dir) or 0
        # timestamp of last modification of .ve/timestamp file (touched by this
        # script
        ve_timestamp_mtime = path.exists(self.ve_timestamp) and path.getmtime(self.ve_timestamp) or 0
        # timestamp of requirements file (pip_packages.txt)
        reqs_timestamp = path.getmtime(self.requirements)
        # if the requirements file is newer than the virtualenv directory,
        # then the virtualenv needs updating
        if ve_dir_mtime < reqs_timestamp:
            return True
        # if the requirements file is newer than the virtualenv timestamp file,
        # then the virtualenv needs updating
        elif ve_timestamp_mtime < reqs_timestamp:
            return True
        else:
            return False

    def update_git_submodule(self):
        """ pip can include directories, and we sometimes add directories as
        submodules.  And pip install will fail if those directories are empty.
        So we need to set up the submodules first. """
        try:
            from project_settings import local_vcs_root, repo_type
        except ImportError:
            print >> sys.stderr, "could not find ve_dir in project_settings.py"
            raise
        if repo_type != 'git':
            return
        subprocess.call(
                ['git', 'submodule', 'update', '--init'],
                cwd=local_vcs_root)

    def delete_virtualenv(self):
        """ delete the virtualenv """
        if path.exists(self.ve_dir):
            shutil.rmtree(self.ve_dir)

    def get_pypi_cache_args(self):
        if self.pypi_cache_url is not None:
            return ['-i', self.pypi_cache_url]
        else:
            return []

    def ensure_virtualenv_exists(self, full_rebuild):
        # if we need to create the virtualenv, then we must do that from
        # outside the virtualenv. The code inside this if statement should only
        # be run outside the virtualenv.
        if full_rebuild and path.exists(self.ve_dir):
            shutil.rmtree(self.ve_dir)
        if not path.exists(self.ve_dir):
            if not self.check_current_python_version():
                print "Running wrong version of python for virtualenv creation"
                return 1
            import virtualenv
            virtualenv.logger = virtualenv.Logger(consumers=[])
            virtualenv.create_environment(self.ve_dir, site_packages=False)
        return 0

    def run_pip_command(self, pip_args, **call_kwargs):
        pip_path = path.join(self.ve_dir, 'bin', 'pip')
        command = [pip_path] + pip_args + self.get_pypi_cache_args()
        try:
            pip_retcode = subprocess.call(command, **call_kwargs)
        except OSError, e:
            print "command failed: %s: %s" % (" ".join(command), e)
            return 1

        if pip_retcode != 0:
            print "command failed: %s" % " ".join(command)

        return pip_retcode

    def update_ve(self, full_rebuild, force_update):
        if not path.exists(self.requirements):
            print >> sys.stderr, "Could not find requirements: file %s" % self.requirements
            return 1

        update_required = self.virtualenv_needs_update()
        if not update_required and not force_update:
            # Nothing to be done
            print "VirtualEnv does not need to be updated"
            print "use --force to force an update"
            return 0

        # if we need to create the virtualenv, then we must do that from
        # outside the virtualenv. This code should only be run outside the
        # virtualenv.
        ve_retcode = self.ensure_virtualenv_exists(full_rebuild)
        if ve_retcode != 0:
            return ve_retcode

        pip_retcode = self.run_pip_command(['install', '-U', 'distribute'])
        if pip_retcode != 0:
            return pip_retcode

        pip_retcode = pip_retcode = self.run_pip_command(
            ['install', '--requirement=%s' % self.requirements],
            cwd=os.path.dirname(self.requirements)
        )
        if pip_retcode == 0:
            self.update_ve_timestamp()

        return pip_retcode

    def go_to_ve(self, file_path, args):
        """
        If running inside virtualenv already, then just return and carry on.

        If not inside the virtualenv then call the virtualenv python, pass it
        the original file and all the arguments to it, so this file will be run
        inside the virtualenv.
        """
        if 'VIRTUAL_ENV' in os.environ:
            # we are in the virtualenv - so carry on to the main code
            return

        if sys.platform == 'win32':
            python = path.join(self.ve_dir, 'Scripts', 'python.exe')
        else:
            python = path.join(self.ve_dir, 'bin', 'python')

        # add environment variable to say we are now in virtualenv
        new_env = os.environ.copy()
        new_env['VIRTUAL_ENV'] = self.ve_dir
        retcode = subprocess.call([python, file_path] + args, env=new_env)
        # call the original using the virtualenv and exit
        sys.exit(retcode)
