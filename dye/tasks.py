#!/usr/bin/env python
#
# This script is to set up various things for our projects. It can be used by:
#
# * developers - setting up their own environment
# * jenkins - setting up the environment and running tests
# * fabric - it will call a copy on the remote server when deploying
#
# The tasks it will do (eventually) include:
#
# * creating, updating and deleting the virtualenv
# * creating, updating and deleting the database (sqlite or mysql)
# * setting up the local_settings stuff
# * running tests
"""This script is to set up various things for our projects. It can be used by:

* developers - setting up their own environment
* jenkins - setting up the environment and running tests
* fabric - it will call a copy on the remote server when deploying

General arguments are:

    -h, --help       Print this help text
    -d, --deploydir  Set the deploy dir (where to find project_settings.py
                     and, optionally, localtasks.py) Defaults to the directory
                     that contains tasks.py
    -t, --task-description <task_name>
                     Print a description of a task and exit
    -q, --quiet      Print less output while executing (note: not none)
    -v, --verbose    Print extra output while executing

You can pass arguments to the tasks listed below, by adding the argument after a
colon. So to call deploy and set the environment to staging you could do:

$ ./tasks.py deploy:staging

or you could name the argument and set the value after an equals sign:

$ ./tasks.py deploy:environment=staging

Multiple arguments are separated by commas:

$ ./tasks.py deploy:environment=staging,arg2=somevalue

You can get a description of a function (the docstring, and a basic
description of the arguments it takes) by using -t thus:

    -t <function_name>

If you need to know more, then you'll have to look at the code of the
function in tasklib.py (or localtasks.py) to see what arguments the
function accepts.
"""

import os
import sys
import getopt
import inspect

from dye import tasklib

localtasks = None


def invalid_command(cmd):
    print "Tasks.py:"
    print
    print "%s is not a valid command" % cmd
    print
    print "For help use --help"


def get_public_callables(mod):
    callables = []
    if mod:
        for task in dir(mod):
            if callable(getattr(mod, task)):
                if not task.startswith('_') and not task.endswith('Error'):
                    callables.append(task)
    return callables


def tasklib_list():
    return get_public_callables(tasklib)


def localtasks_list():
    return get_public_callables(localtasks)


def tasks_available():
    tasks = list(set(tasklib_list() + localtasks_list()))
    tasks.sort()
    return tasks


def print_help_text():
    print __doc__
    print "The functions you can call are:"
    print
    tasks = tasks_available()
    for task in tasks:
        print task
    print


def print_description(task_name, task_function):
    print "%s:" % task_name
    print
    if task_function.func_doc is not None:
        print task_function.func_doc
    else:
        print "No description found for %s" % task_name
    print
    argspec = inspect.getargspec(task_function)
    if len(argspec.args) == 0:
        if argspec.varargs is None:
            print "%s takes no arguments." % task_name
        else:
            print "%s takes no named arguments, but instead takes a variable " % task_name
            print "number of arguments."
    else:
        print "Arguments taken by %s:" % task_name
        for arg in argspec.args:
            print "* %s" % arg
        if argspec.varargs is not None:
            print
            print "You can also add a variable number of arguments."
    print


def describe_task(args):
    for arg in args:
        task = arg.split(':', 1)[0]
        if hasattr(localtasks, task):
            taskf = getattr(localtasks, task)
            print_description(task, taskf)
        elif hasattr(tasklib, task):
            taskf = getattr(tasklib, task)
            print_description(task, taskf)
        else:
            print "%s: no such task found" % task
            print


def convert_args(value):
    if value.lower() == 'true':
        return True
    elif value.lower() == 'false':
        return False
    elif value.isdigit():
        return int(value)
    else:
        return value


def main(argv):
    global localtasks
    verbose = False
    quiet = False
    deploy_dir = os.path.dirname(__file__)
    # parse command line options
    try:
        opts, args = getopt.getopt(argv[1:], "thd:qv",
                ["task-description", "help", "deploydir=", "quiet", "verbose"])
    except getopt.error, msg:
        print msg
        print "for help use --help"
        return 2
    # process options
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print_help_text()
            return 0
        if opt in ("-v", "--verbose"):
            verbose = True
        if opt in ("-q", "--quiet"):
            quiet = True
        if opt in ("-t", "--task-description"):
            describe_task(args)
            return 0
        if opt in ("-d", "--deploydir"):
            deploy_dir = arg
    if verbose and quiet:
        print "Cannot set both verbose and quiet"
        return 2
    tasklib.env['verbose'] = verbose
    tasklib.env['quiet'] = quiet
    tasklib.env['deploy_dir'] = deploy_dir

    sys.path.append(deploy_dir)
    import project_settings
    # now see if we can find localtasks
    # We deliberately don't surround the import by try/except. If there
    # is an error in localfab, you want it to blow up immediately, rather
    # than silently fail.
    if os.path.isfile(os.path.join(deploy_dir, 'localtasks.py')):
        import localtasks
        if (hasattr(localtasks, '_setup_paths')):
            localtasks._setup_paths()
    # now set up the various paths required
    tasklib._setup_paths(project_settings, localtasks)
    if len(args) == 0:
        print_help_text()
        return 0
    # process arguments - just call the function with that name
    for arg in args:
        task_bits = arg.split(':', 1)
        fname = task_bits[0]
        # work out which function to call - localtasks have priority
        f = None
        if fname in localtasks_list():
            f = getattr(localtasks, fname)
        elif fname in tasklib_list():
            f = getattr(tasklib, fname)
        else:
            invalid_command(fname)
            return 2

        # call the function
        try:
            if len(task_bits) == 1:
                f()
            else:
                f_args = task_bits[1].split(',')
                pos_args = [convert_args(arg) for arg in f_args if arg.find('=') == -1]
                kwargs = [arg for arg in f_args if arg.find('=') >= 0]
                kwargs_dict = {}
                for kwarg in kwargs:
                    kw, value = kwarg.split('=', 1)
                    kwargs_dict[kw] = convert_args(value)
                f(*pos_args, **kwargs_dict)
        except tasklib.TasksError as e:
            print >>sys.stderr, e.msg
            return e.exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv))
