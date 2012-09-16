#!/usr/bin/env python
# a script to set up the virtualenv so we can use fabric and tasks

import os, sys, subprocess
import project_settings

current_dir = os.path.dirname(__file__)
# this directory should contain the virtualenv
ve_dir = os.path.join(current_dir, '..', project_settings.django_relative_dir, '.ve')

if not os.path.exists(ve_dir):
    print "Expected virtualenv does not exist"
    print "(required for correct version of fabric and dye)"
    print "Please run './bootstrap.sh' to create virtualenv"
    sys.exit(1)

fab_bin = os.path.join(ve_dir, 'bin', 'fab')
# depending on how you've installed dye, you may need to edit this line
fabfile = os.path.join(ve_dir, 'src', 'package', 'dye', 'fabfile.py')

# call the fabric in the virtual env
fab_call = [fab_bin]
# tell it to use the fabfile from dye
fab_call += ['-f', fabfile]
# tell fabric that this directory is where it can find project_settings and
# localfab (if it exists)
fab_call += ['projectdir:' + current_dir]
# add any arguments passed to this script
fab_call += sys.argv[1:]
# exit with the fabric exit code
sys.exit(subprocess.call(fab_call))
