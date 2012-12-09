#!/usr/bin/env python
# a script to set up the virtualenv so we can use fabric and tasks

import os, sys, subprocess

current_dir = os.path.dirname(__file__)
# this directory should contain the virtualenv
ve_dir = os.path.join(current_dir, '.ve.deploy')

if not os.path.exists(ve_dir):
    print "Expected virtualenv does not exist"
    print "(required for correct version of fabric and dye)"
    print "Please run './bootstrap.sh' to create virtualenv"
    sys.exit(1)

fab_bin = os.path.join(ve_dir, 'bin', 'fab')

# depending on how you've installed dye, you may need to edit this line

# the below is for an "editable" install, what you get from the following
# line in pip_packages.txt
# -e git+git://github.com/aptivate/dye.git
fabfile = os.path.join(ve_dir, 'src', 'package', 'dye', 'fabfile.py')

# alternatively here is the path for non-editable install
#fabfile = os.path.join(ve_dir, 'lib', 'python2.6', 'site-packages', 'dye', 'fabfile.py')

# tell fabric that this directory is where it can find project_settings and
# localfab (if it exists)
osenv = os.environ
osenv['DEPLOYDIR'] = current_dir

# call the fabric in the virtual env
fab_call = [fab_bin]
# tell it to use the fabfile from dye
fab_call += ['-f', fabfile]
# add any arguments passed to this script
fab_call += sys.argv[1:]

# exit with the fabric exit code
try:
    sys.exit(subprocess.call(fab_call, env=osenv))
except OSError as e:
    raise Exception("Failed to execute %s: %s" % (fab_call, e))
