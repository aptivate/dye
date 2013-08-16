#!/usr/bin/env python
"""This script is to set up various things for our projects. It can be used by:

* developers - setting up their own environment
* jenkins - setting up the environment and running tests
* fabric - it will call a copy on the remote server when deploying

Usage:
    tasks.py [-d DEPLOYDIR] [options] <tasks>...
    tasks.py [-d DEPLOYDIR] -h | --help

Options:
    -t, --task-description     Describe the tasks instead of running them.  This
                               will show the task docstring and a basic
                               description of the arguments it takes.
    -d, --deploydir DEPLOYDIR  Set the deploy dir (where to find project_settings.py
                               and, optionally, localtasks.py)  Defaults to the
                               directory that contains tasks.py
    -q, --quiet                Print less output while executing (note: not none)
    -v, --verbose              Print extra output while executing
    -h, --help                 Print this help text

You can pass arguments to the tasks listed below, by adding the argument after a
colon. So to call deploy and set the environment to staging you could do:

$ ./tasks.py deploy:staging

or you could name the argument and set the value after an equals sign:

$ ./tasks.py deploy:environment=staging

Multiple arguments are separated by commas:

$ ./tasks.py deploy:environment=staging,arg2=somevalue
"""

import os
import sys
import docopt
import inspect

from dye import tasklib
from dye.tasklib.exceptions import TasksError

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
        # getmembers returns a list of tuples of from ('name', <function>)
        all_functions = inspect.getmembers(mod, inspect.isfunction)
        callables = [func[0] for func in all_functions
                if not func[0].startswith('_')]
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


def convert_argument(value):
    if value.lower() == 'true':
        return True
    elif value.lower() == 'false':
        return False
    elif value.isdigit():
        return int(value)
    else:
        return value


def convert_task_bits(task_bits):
    """
    Take something like:

        my_task:val1,true,arg1=hello,arg2=3

    and convert it into the name, args and kwargs, so:

        (my_task, ('val1', True), {'arg1': 'hello', 'arg2': 3})

    Note that the 3 is converted into a number and 'true' is converted to boolean True
    """
    if ':' not in task_bits:
        return task_bits, (), {}
    task, args = task_bits.split(':', 1)
    args_list = args.split(',')

    pos_args = [convert_argument(arg) for arg in args_list if arg.find('=') == -1]

    kwargs = [arg for arg in args_list if arg.find('=') >= 0]
    kwargs_dict = {}
    for kwarg in kwargs:
        kw, value = kwarg.split('=', 1)
        kwargs_dict[kw] = convert_argument(value)

    return task, pos_args, kwargs_dict


def main(argv):
    global localtasks

    options = docopt.docopt(__doc__, argv, help=False)

    # need to set this before doing task-description or help
    if options['--deploydir']:
        tasklib.env['deploy_dir'] = options['--deploydir']
    else:
        tasklib.env['deploy_dir'] = os.path.dirname(__file__)
    # first we need to find and load the project settings
    sys.path.append(tasklib.env['deploy_dir'])
    # now see if we can find localtasks
    # We deliberately don't surround the import by try/except. If there
    # is an error in localfab, you want it to blow up immediately, rather
    # than silently fail.
    if os.path.isfile(os.path.join(tasklib.env['deploy_dir'], 'localtasks.py')):
        import localtasks

    if options['--help']:
        print_help_text()
        return 0
    if options['--task-description']:
        describe_task(options['<tasks>'])
        return 0
    if options['--verbose'] and options['--quiet']:
        print "Cannot set both verbose and quiet"
        return 2
    tasklib.env['verbose'] = options['--verbose']
    tasklib.env['quiet'] = options['--quiet']

    try:
        import project_settings
    except ImportError:
        print >>sys.stderr, \
            "Could not import project_settings - check your --deploydir argument"
        return 1

    if localtasks is not None:
        if (hasattr(localtasks, '_setup_paths')):
            localtasks._setup_paths()
    # now set up the various paths required
    tasklib._setup_paths(project_settings, localtasks)
    # process arguments - just call the function with that name
    for arg in options['<tasks>']:
        fname, pos_args, kwargs = convert_task_bits(arg)
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
            f(*pos_args, **kwargs)
        except TasksError as e:
            print >>sys.stderr, e.msg
            return e.exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
