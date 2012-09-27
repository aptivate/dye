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

# depending on how you've installed dye, you may need to edit this line
tasks = os.path.join(ve_dir, 'src', 'package', 'dye', 'tasks.py')

# call the tasks.py in the virtual env
tasks_call = [tasks]
# tell tasks.py that this directory is where it can find project_settings and
# localtasks (if it exists)
tasks_call += ['--projectdir=' + current_dir]
# add any arguments passed to this script
tasks_call += sys.argv[1:]
# exit with the tasks.py exit code
sys.exit(subprocess.call(tasks_call))

