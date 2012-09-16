#!/usr/bin/env python
# a script to set up the virtualenv so we can use fabric and tasks

import os, sys, subprocess

import project_settings

django_dir = os.path.join(os.path.dirname(__file__), '..', project_settings.django_relative_dir)

python26 = os.path.join('/', 'usr', 'bin', 'python2.6')
python27 = os.path.join('/', 'usr', 'bin', 'python2.7')
generic_python = os.path.join('/', 'usr', 'bin', 'python')
paths_to_try = (python26, python27, generic_python, sys.executable)
chosen_python = None
for python in paths_to_try:
    if os.path.exists(python):
        chosen_python = python
if chosen_python is None:
    raise Exception("Failed to find a valid Python executable " +
            "in any of these locations: %s" % paths_to_try)

manage_py = os.path.join(django_dir, 'manage.py')

subprocess.call([chosen_python, manage_py, 'update_ve'])
