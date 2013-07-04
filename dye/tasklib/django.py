import os
from os import path
import random
import subprocess

from .exceptions import InvalidProjectError, ShellCommandError
from .util import _check_call_wrapper
# global dictionary for state
from .environment import env


def _manage_py(args, cwd=None):
    # for manage.py, always use the system python
    # otherwise the update_ve will fail badly, as it deletes
    # the virtualenv part way through the process ...
    manage_cmd = [env['python_bin'], env['manage_py']]
    if env['quiet']:
        manage_cmd.append('--verbosity=0')
    if isinstance(args, str):
        manage_cmd.append(args)
    else:
        manage_cmd.extend(args)

    # Allow manual specification of settings file
    if 'manage_py_settings' in env:
        manage_cmd.append('--settings=%s' % env['manage_py_settings'])

    if cwd is None:
        cwd = env['django_dir']

    if env['verbose']:
        print 'Executing manage command: %s' % ' '.join(manage_cmd)
    output_lines = []
    try:
        # TODO: make compatible with python 2.3
        popen = subprocess.Popen(manage_cmd, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    except OSError, e:
        print "Failed to execute command: %s: %s" % (manage_cmd, e)
        raise e
    for line in iter(popen.stdout.readline, ""):
        if env['verbose']:
            print line,
        output_lines.append(line)
    returncode = popen.wait()
    if returncode != 0:
        error_msg = "Failed to execute command: %s: returned %s\n%s" % \
            (manage_cmd, returncode, "\n".join(output_lines))
        raise ShellCommandError(error_msg, popen.returncode)
    return output_lines


def link_local_settings(environment):
    """ link local_settings.py.environment as local_settings.py """
    if not env['quiet']:
        print "### creating link to local_settings.py"

    # check that settings imports local_settings, as it always should,
    # and if we forget to add that to our project, it could cause mysterious
    # failures
    settings_file_path = path.join(env['django_settings_dir'], 'settings.py')
    if not(path.isfile(settings_file_path)):
        raise InvalidProjectError("Fatal error: settings.py doesn't seem to exist")
    with open(settings_file_path) as settings_file:
        matching_lines = [line for line in settings_file if 'local_settings' in line]
    if not matching_lines:
        raise InvalidProjectError("Fatal error: settings.py doesn't seem to import "
            "local_settings.*: %s" % settings_file_path)

    source = path.join(env['django_settings_dir'], 'local_settings.py.%s' %
        environment)
    target = path.join(env['django_settings_dir'], 'local_settings.py')

    # die if the correct local settings does not exist
    if not path.exists(source):
        raise InvalidProjectError("Could not find file to link to: %s" % source)

    # remove any old versions, plus the pyc copy
    for old_file in (target, target + 'c'):
        if path.exists(old_file):
            os.remove(old_file)

    if os.name == 'posix':
        os.symlink('local_settings.py.%s' % environment, target)
    elif os.name == 'nt':
        try:
            import win32file
        except ImportError:
            raise Exception(
                "It looks like the PyWin32 extensions are not installed")
        try:
            win32file.CreateSymbolicLink(target, source)
        except NotImplementedError:
            win32file.CreateHardLink(target, source)
    else:
        import shutil
        shutil.copy2(source, target)
    env['environment'] = environment


def create_private_settings():
    """ create private settings file
    - contains generated DB password and secret key"""
    private_settings_file = path.join(env['django_settings_dir'],
                                    'private_settings.py')
    if not path.exists(private_settings_file):
        if not env['quiet']:
            print "### creating private_settings.py"
        # don't use "with" for compatibility with python 2.3 on whov2hinari
        f = open(private_settings_file, 'w')
        try:
            secret_key = "".join([random.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for i in range(50)])
            db_password = "".join([random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for i in range(12)])

            f.write("SECRET_KEY = '%s'\n" % secret_key)
            f.write("DB_PASSWORD = '%s'\n" % db_password)
        finally:
            f.close()
        # need to think about how to ensure this is owned by apache
        # despite having been created by root
        #os.chmod(private_settings_file, 0400)


def collect_static():
    return _manage_py(["collectstatic", "--noinput"])


def _install_django_jenkins():
    """ ensure that pip has installed the django-jenkins thing """
    if not env['quiet']:
        print "### Installing Jenkins packages"
    pip_bin = path.join(env['ve_dir'], 'bin', 'pip')
    cmds = [
        [pip_bin, 'install', 'django-jenkins'],
        [pip_bin, 'install', 'pylint'],
        [pip_bin, 'install', 'coverage']]

    for cmd in cmds:
        _check_call_wrapper(cmd)


def _manage_py_jenkins():
    """ run the jenkins command """
    args = ['jenkins', ]
    args += ['--pylint-rcfile', path.join(env['vcs_root_dir'], 'jenkins', 'pylint.rc')]
    coveragerc_filepath = path.join(env['vcs_root_dir'], 'jenkins', 'coverage.rc')
    if path.exists(coveragerc_filepath):
        args += ['--coverage-rcfile', coveragerc_filepath]
    args += env['django_apps']
    if not env['quiet']:
        print "### Running django-jenkins, with args; %s" % args
    _manage_py(args, cwd=env['vcs_root_dir'])
