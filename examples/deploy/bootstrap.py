#!/usr/bin/env python
# a script to set up the virtualenv so we can use fabric and tasks

import os, sys, subprocess

PACKAGES = [
    'fabric==1.4',
    '-e git+git://github.com/aptivate/dye.git#egg=Package',
    ]

def find_python():
    """ work out which python to use """
    generic_python = os.path.join('/', 'usr', 'bin', 'python')
    python26 = generic_python + '2.6'
    python27 = generic_python + '2.7'
    paths_to_try = (python27, python26, generic_python, sys.executable)
    chosen_python = None
    for python in paths_to_try:
        if os.path.exists(python):
            chosen_python = python
    if chosen_python is None:
        raise Exception("Failed to find a valid Python executable " +
                "in any of these locations: %s" % paths_to_try)
    return chosen_python

def create_virtualenv(ve_dir):
    # use the python we want
    # ensure we don't end up with the system python
    python_bin = find_python()
    ve_cmd = ['virtualenv',
        '-python_bin=' + python_bin,
        '--no-site-packages',
        ve_dir,
        ]
    subprocess.check_call(ve_cmd)

def main():
    current_dir = os.path.dirname(__file__)
    ve_dir = os.path.join(current_dir, '.ve.deploy')

    # check if virtualenv exists
    if os.path.isdir(ve_dir):
        # if it does, offer to recreate
        choice = raw_input("deploy virtualenv already exists, do you want to recreate it? (y|N) ")
        if len(choice) == 0 or choice[0].lower() != 'y':
            return 0
        # remove old ve
        import shutil
        shutil.rmtree(ve_dir)

    # create the virtualenv and fill it
    create_virtualenv(ve_dir)

    # TODO: could now print instructions for local deploy and fab deploy ...

if __name__ == '__main__':
    sys.exit(main())
