#!/usr/bin/env python
# a script to set up the virtualenv so we can use fabric and tasks

import os, sys, subprocess
import project_settings

# this directory should contain the virtualenv
ve_dir = os.path.join(os.dirname(__file__), '..', project_settings.django_dir, '.ve')

fab_bin = os.path.join(ve_dir, 'bin', 'fab')
fabfile = os.path.join(ve_dir, 'src', 'Dye', 'dye', 'fabfile.py')

subprocess.call([fab_bin, '-f', fabfile] + sys.argv[1:])
