import os
from os import path

from .exceptions import InvalidProjectError
from .environment import env


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
