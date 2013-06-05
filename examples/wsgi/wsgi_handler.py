import os
from os import path
import sys
import site

vcs_root_dir = path.abspath(path.join(path.dirname(__file__), '..'))

# add deploy dir to path so we can import project_settings
sys.path.append(path.join(vcs_root_dir, 'deploy'))
from project_settings import project_name, relative_django_dir, relative_ve_dir

# ensure the virtualenv for this instance is added
python = 'python%d.%d' % (sys.version_info[0], sys.version_info[1])
site.addsitedir(
    path.join(vcs_root_dir, relative_ve_dir, 'lib', python, 'site-packages'))

sys.path.append(path.join(vcs_root_dir, relative_django_dir))

# edit as required
os.environ['DJANGO_SETTINGS_MODULE'] = project_name + '.settings'
#os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django.core.handlers.wsgi

application = django.core.handlers.wsgi.WSGIHandler()
