import os
from os import path
from datetime import datetime
import getpass
import re

from fabric.context_managers import cd, hide, settings
from fabric.operations import require, prompt, get, run, sudo, local, put
from fabric.state import env
from fabric.contrib import files
from fabric import utils


def _setup_paths(project_settings):
    # first merge in variables from project_settings - but ignore __doc__ etc
    user_settings = [x for x in vars(project_settings).keys() if not x.startswith('__')]
    for setting in user_settings:
        env.setdefault(setting, vars(project_settings)[setting])

    # set the timestamp - used for directory names at least
    env.timestamp = datetime.now()
    # we want the first use of sudo to be for something where we don't
    # read the result
    env.sudo_has_been_used = False

    # allow for project_settings having set up some of these differently
    env.setdefault('verbose', False)
    env.setdefault('use_sudo', True)
    env.setdefault('cvs_rsh', 'CVS_RSH="ssh"')
    env.setdefault('default_branch', {'production': 'master', 'staging': 'master'})
    env.setdefault('server_project_home',
                   path.join(env.server_home, env.project_name))
    env.setdefault('current_link', path.join(env.server_project_home, 'current'))
    env.setdefault('vcs_root_dir', env.current_link)
    env.setdefault('next_dir', path.join(env.server_project_home, _create_timestamp_dirname(env.timestamp)))
    env.setdefault('dump_dir', path.join(env.server_project_home, 'dbdumps'))
    env.setdefault('relative_deploy_dir', 'deploy')
    env.setdefault('deploy_dir', path.join(env.vcs_root_dir, env.relative_deploy_dir))
    env.setdefault('settings', '%(project_name)s.settings' % env)
    env.setdefault('relative_webserver_dir', env.webserver)

    if env.project_type == "django":
        env.setdefault('relative_django_dir', env.project_name)
        env.setdefault('relative_django_settings_dir', env['relative_django_dir'])
        env.setdefault('relative_ve_dir', path.join(env['relative_django_dir'], '.ve'))

        env.setdefault('relative_wsgi_dir', 'wsgi')

        # now create the absolute paths of everything else
        env.setdefault('django_dir',
                       path.join(env['vcs_root_dir'], env['relative_django_dir']))
        env.setdefault('django_settings_dir',
                       path.join(env['vcs_root_dir'], env['relative_django_settings_dir']))
        env.setdefault('ve_dir',
                       path.join(env['vcs_root_dir'], env['relative_ve_dir']))
        env.setdefault('manage_py', path.join(env['django_dir'], 'manage.py'))

    # local_tasks_bin is the local copy of tasks.py
    # this should be the copy from where ever fab.py is being run from ...
    if 'DEPLOYDIR' in os.environ:
        env.setdefault('local_tasks_bin',
                       path.join(os.environ['DEPLOYDIR'], 'tasks.py'))
    else:
        env.setdefault('local_tasks_bin',
                       path.join(path.dirname(__file__), 'tasks.py'))


def _linux_type():
    if 'linux_type' not in env:
        # work out if we're based on redhat or centos
        # TODO: look up stackoverflow question about this.
        if files.exists('/etc/redhat-release'):
            env.linux_type = 'redhat'
        elif files.exists('/etc/debian_version'):
            env.linux_type = 'debian'
        else:
            # TODO: should we print a warning here?
            utils.abort("could not determine linux type of server we're deploying to")
    return env.linux_type


def _get_python():
    if 'python_bin' not in env:
        python_bin = path.join('/', 'usr', 'bin', 'python')
        python26 = python_bin + '2.6'
        python27 = python_bin + '2.7'
        if files.exists(python27):
            env.python_bin = python27
        elif files.exists(python26):
            env.python_bin = python26
        else:
            env.python_bin = python_bin
    return env.python_bin


def _get_tasks_bin():
    require('deploy_dir', provided_by=env.valid_envs)
    if 'tasks_bin' not in env:
        env.tasks_bin = path.join(env.deploy_dir, 'tasks.py')
    return env.tasks_bin


def _tasks(tasks_args, verbose=False):
    tasks_cmd = _get_tasks_bin()
    if env.verbose or verbose:
        tasks_cmd += ' -v'
    return sudo_or_run(tasks_cmd + ' ' + tasks_args)


def _get_svn_user_and_pass():
    if 'svnuser' not in env or len(env.svnuser) == 0:
        # prompt user for username
        prompt('Enter SVN username:', 'svnuser')
    if 'svnpass' not in env or len(env.svnpass) == 0:
        # prompt user for password
        env.svnpass = getpass.getpass('Enter SVN password:')


def _local_is_file_writable(filename):
    try:
        # use 'a' for append - if we use 'w' then we truncate the file
        # (ie we delete any existing content)
        f = open(filename, 'a')
        f.close()
        return True
    except IOError:
        return False


def verbose(verbose=True):
    """Set verbose output"""
    env.verbose = verbose


def deploy_clean(revision=None):
    """ delete the entire install and do a clean install """
    if env.environment == 'production':
        utils.abort('do not delete the production environment!!!')
    # TODO: dump before cleaning database?
    with settings(warn_only=True):
        webserver_cmd('stop')
    clean_db()
    clean_files()
    deploy(revision)


def clean_files():
    require('server_project_home', provided_by=env.valid_envs)
    sudo_or_run('rm -rf %s' % env.server_project_home)


def _create_dir_if_not_exists(path):
    if not files.exists(path):
        sudo_or_run('mkdir -p %s' % path)


def deploy(revision=None, keep=None, full_rebuild=True):
    """ update remote host environment (virtualenv, deploy, update)

    It takes three arguments:

    * revision is the VCS revision ID to checkout (if not specified then
      the latest will be checked out)
    * keep is the number of old versions to keep around for rollback (default
      5)
    * full_rebuild is whether to do a full rebuild of the virtualenv
    """
    require('project_type', 'server_project_home', provided_by=env.valid_envs)

    # this really needs to be first - other things assume the directory exists
    _create_dir_if_not_exists(env.server_project_home)

    # if the <server_project_home>/previous/ directory doesn't exist, this does
    # nothing
    _migrate_directory_structure()
    _set_vcs_root_dir_timestamp()

    check_for_local_changes(revision)
    # TODO: check for deploy-in-progress.json file
    # also check if there are any directories newer than current ???
    # might just mean we did a rollback, so maybe don't bother as the
    # deploy-in-progress should be enough
    # _check_for_deploy_in_progress()

    # TODO: create deploy-in-progress.json file
    # _set_deploy_in_progress()
    create_copy_for_next()
    checkout_or_update(in_next=True, revision=revision)
    # remove any old pyc files - essential if the .py file is removed by VCS
    if env.project_type == "django":
        rm_pyc_files(path.join(env.next_dir, env.relative_django_dir))
    # create the deploy virtualenv if we use it
    create_deploy_virtualenv(in_next=True, full_rebuild=full_rebuild)

    # we only have to disable this site after creating the rollback copy
    # (do this so that apache carries on serving other sites on this server
    # and the maintenance page for this vhost)
    downtime_start = datetime.now()
    link_webserver_conf(maintenance=True)
    with settings(warn_only=True):
        webserver_cmd('reload')
    # TODO: do a database dump in the old directory
    point_current_to_next()

    # Use tasks.py deploy:env to actually do the deployment, including
    # creating the virtualenv if it thinks it necessary, ignoring
    # env.use_virtualenv as tasks.py knows nothing about it.
    _tasks('deploy:' + env.environment)

    # bring this vhost back in, reload the webserver and touch the WSGI
    # handler (which reloads the wsgi app)
    link_webserver_conf()
    webserver_cmd('reload')
    downtime_end = datetime.now()
    touch_wsgi()

    delete_old_rollback_versions(keep)
    if env.environment == 'production':
        setup_db_dumps()

    # TODO: _remove_deploy_in_progress()
    # move the deploy-in-progress.json file into the old directory as
    # deploy-details.json
    _report_downtime(downtime_start, downtime_end)


def _total_seconds(td):
    """python 2.7 has a total_seconds() method, but before doesn't """
    if hasattr(td, 'total_seconds'):
        return td.total_seconds()
    else:
        return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


def _report_downtime(downtime_start, downtime_end):
    downtime = downtime_end - downtime_start
    utils.puts("Downtime lasted for %.1f seconds" % _total_seconds(downtime))
    utils.puts("(Downtime started at %s and finished at %s)" %
               (downtime_start, downtime_end))


def set_up_celery_daemon():
    require('vcs_root_dir', 'project_name', provided_by=env)
    for command in ('celerybeat', 'celeryd'):
        command_project = command + '_' + env.project_name
        celery_run_script_location = path.join(env['vcs_root_dir'],
                                               'celery', 'init', command)
        celery_run_script = path.join('/etc', 'init.d', command_project)
        celery_configuration_location = path.join(env['vcs_root_dir'],
                                                  'celery', 'config', command)
        celery_configuration_destination = path.join('/etc', 'default',
                                                     command_project)

        sudo_or_run(" ".join(['cp', celery_run_script_location,
                    celery_run_script]))
        sudo_or_run(" ".join(['chmod', '+x', celery_run_script]))

        sudo_or_run(" ".join(['cp', celery_configuration_location,
                    celery_configuration_destination]))
        sudo_or_run('/etc/init.d/%s restart' % command_project)


def clean_old_celery():
    """As the scripts have moved location you might need to get rid of old
    versions of celery."""
    require('vcs_root_dir', provided_by=env)
    for command in ('celerybeat', 'celeryd'):
        celery_run_script = path.join('/etc', 'init.d', command)
        if files.exists(celery_run_script):
            sudo_or_run('/etc/init.d/%s stop' % command)
            sudo_or_run('rm %s' % celery_run_script)

        celery_configuration_destination = path.join('/etc', 'default', command)
        if files.exists(celery_configuration_destination):
            sudo_or_run('rm %s' % celery_configuration_destination)


def _create_timestamp_dirname(timestamp=None):
    if timestamp is None:
        timestamp = datetime.now()
    return timestamp.strftime("%Y-%m-%d_%H-%M-%S")


def _migrate_directory_structure():
    """ The new directory structure is timestamp directories in server project
    home, with the timestamp being the time that directory was deployed.  A
    soft link named current/ will point at the version that apache will serve.
    For backwards compatibility with apache config, a dev/ link will also be
    created, pointing at current/

    The old was timestamp directories in <server project home>/previous/ with
    the timestamp being the time the directory was archived.  The current
    deploy was in <server project home>/dev/"""
    # check if the README is present
    require('server_project_home', provided_by=env)
    readme_path = path.join(env.server_project_home, 'README.mkd')
    if not files.exists(readme_path):
        local_readme_path = path.join(path.dirname(path.realpath(__file__)),
                                      'static', 'README-server-project-home.mkd')
        put(local_readme_path, readme_path, use_sudo=env.use_sudo)

    prev_root = path.join(env.server_project_home, 'previous')
    if not files.exists(prev_root):
        return
    # the if v at the end is to filter any empty strings (say if output of
    # run(...) ends in \n )
    prev_versions = [v.strip() for v in
                     run('ls -1 ' + prev_root).split('\n')
                     if v.startswith('20')]

    # first move the current version to the newest timestamp and create the
    # links required
    old_vcs_root = path.join(env.server_project_home, 'dev')
    new_vcs_root = path.join(env.server_project_home, prev_versions[-1])
    sudo_or_run('mv %s %s' % (old_vcs_root, new_vcs_root))
    with cd(env.server_project_home):
        # create the current link so we know which apache should serve
        sudo_or_run('ln -s %s current' % prev_versions[-1])
        # create the dev link for backwards compatibility
        sudo_or_run('ln -s current dev')

    # next move the previous versions along, but move them back a timestamp
    # and also move the repo from inside the dev directory to being the
    # directory, and don't forget the sql dump
    for i in range(len(prev_versions) - 1):
        sudo_or_run('mv %s/dev %s' % (
            path.join(prev_root, prev_versions[i + 1]),
            path.join(env.server_project_home, prev_versions[i])
        ))
        sudo_or_run('mv %s/db_dump.sql %s' % (
            path.join(prev_root, prev_versions[i + 1]),
            path.join(env.server_project_home, prev_versions[i])
        ))

    # and finally delete the previous/ directory altogether
    sudo_or_run('rm -rf %s' % prev_root)


def _set_vcs_root_dir_timestamp():
    """ Find what the real directory name is that current/ points to. """
    if files.exists(env.vcs_root_dir):
        env.vcs_root_dir_timestamp = sudo_or_run('readlink -f %s' % env.vcs_root_dir)
    else:
        # TODO: review what uses this and how it will cope with a value of None
        env.vcs_root_dir_timestamp = None


def _fix_virtualenv_paths():
    """The virtualenv bin/ files have the absolute directory hardwired
    into them, as do site-packages/easy-install.pth and site-packages/*.egg-link
    We need to change the name of the directory - which in our case means
    replacing the timestamp.
    """
    require('next_dir', 'relative_ve_dir', provided_by=env)
    ve_bin_dir = path.join(env.next_dir, env.relative_ve_dir, 'bin')
    # the expected result of this is, say:
    # /var/django/project_name/2013-10-13_12-13-14/django/website/.ve/lib/python2.6
    # the * on the end is to match any/all python versions
    ve_lib_python = sudo_or_run(
        'ls -d %s*' % path.join(env.next_dir, env.relative_ve_dir, 'lib', 'python'))
    ve_site_packages_dir = path.join(ve_lib_python, 'site-packages')

    old_timestamp = path.basename(env.vcs_root_dir_timestamp)
    new_timestamp = _create_timestamp_dirname(env.timestamp)
    cmd = "sed -i 's/%s/%s/' *" % (old_timestamp, new_timestamp)
    with cd(ve_bin_dir):
        sudo_or_run(cmd)
    with cd(ve_site_packages_dir):
        sudo_or_run(cmd + '.pth')
        sudo_or_run(cmd + '.egg-link')


def create_copy_for_next():
    """Copy the current version to "next" so that we can do stuff like
    the VCS update and virtualenv update without taking the site offline"""
    require('next_dir', 'vcs_root_dir', provided_by=env)
    # check if next directory already exists
    # if it does maybe there was an aborted deploy, or maybe someone else is
    # deploying.  Either way, stop and ask the user what to do.
    if files.exists(env.next_dir):
        utils.warn('The "next" directory already exists.  Maybe a previous '
                   'deploy failed, or maybe another deploy is in progress.')
        continue_anyway = prompt('Would you like to continue anyway '
                                 '(and delete the current next dir)? [no/yes]',
                default='no', validate='^no|yes$')
        if continue_anyway.lower() != 'yes':
            utils.abort("Aborting deploy - try again when you're certain what to do.")
        sudo_or_run('rm -rf %s' % env.next_dir)

    # if this is the initial deploy, the vcs_root_dir won't exist yet. In that
    # case, don't create it (otherwise the checkout code will get confused).
    if files.exists(env.vcs_root_dir):
        # cp -a - amongst other things this preserves links and timestamps
        # so the compare that bootstrap.py does to see if the virtualenv
        # needs an update should still work.
        sudo_or_run('cp -a %s %s' % (env.vcs_root_dir_timestamp, env.next_dir))

        # fix the virtualenv
        _fix_virtualenv_paths()


def point_current_to_next():
    """ Change the soft link `current` to point to the new next_dir """
    # dump the database in the old directory - do this before we remove
    # the current link
    require('current_link', 'vcs_root_dir_timestamp', provided_by=env)
    _dump_db_in_directory(env.vcs_root_dir_timestamp)
    if files.exists(env.current_link):
        sudo_or_run('rm %s' % env.current_link)
    with cd(env.server_project_home):
        sudo_or_run('ln -s %s current' % env.next_dir)


def _dump_db_in_directory(dump_dir):
    require('django_settings_dir', 'project_type', provided_by=env.valid_envs)
    if (env.project_type == 'django' and
            files.exists(path.join(env.django_settings_dir, 'local_settings.py'))):
        # dump database (provided local_settings has been set up properly)
        with cd(dump_dir):
            # just in case there is some other reason why the dump fails
            with settings(warn_only=True):
                dump_result = _tasks('dump_db')
            if dump_result.succeeded:
                # and compress the dump (provided it worked)
                dump_file = 'db_dump.sql'
                dump_file_compressed = dump_file + '.gz'
                sudo_or_run('gzip -c %s > %s' % (dump_file, dump_file_compressed))
                sudo_or_run('rm %s' % dump_file)


def _get_list_of_versions():
    require('server_project_home', provided_by=env.valid_envs)
    with cd(env.server_project_home):
        versions = run('ls -1')
    # we're expecting timestamps, so this test will be safe until 2100
    return [v.strip() for v in versions.split('\n') if v.startswith('20')]


def delete_old_rollback_versions(keep=None):
    """ Delete old rollback directories, keeping the last "keep" (default 5)".
    """
    require('server_project_home', provided_by=env.valid_envs)
    if keep is None:
        if 'versions_to_keep' in env:
            keep = env.versions_to_keep
        else:
            keep = 5
    # ensure we have a number rather than a string
    keep = int(keep)
    if keep == 0:
        return
    # add 1 as we want the current copy plus keep old copies
    versions_to_keep = -1 * (keep + 1)

    version_list = _get_list_of_versions()
    # mylist[:-6] would be the list missing the last 6 elements
    versions_to_delete = version_list[:versions_to_keep]
    for version_to_delete in versions_to_delete:
        sudo_or_run('rm -rf ' + path.join(
            env.server_project_home, version_to_delete))


def list_versions():
    """List the previous versions available to rollback to."""
    # could also determine the VCS revision number
    _set_vcs_root_dir_timestamp()
    version_list = _get_list_of_versions()
    utils.puts('Available versions are:')
    for version in version_list:
        utils.puts(version)
    utils.puts('Current version is %s' % env.vcs_root_dir_timestamp)


def rollback(version='last', migrate=False, restore_db=False):
    """Redeploy one of the old versions.

    Arguments are 'version', 'migrate' and 'restore_db':

    * if version is 'last' (the default) then the most recent version will be
      restored. Otherwise specify by timestamp - use list_versions to get a
      list of available versions.
    * if restore_db is True, then the database will be restored as well as the
      code. The default is False.
    * if migrate is True, then fabric will attempt to work out the new and old
      migration status and run the migrations to match the database versions.
      The default is False

    Note that migrate and restore_db cannot both be True."""
    require('server_project_home', 'vcs_root_dir', 'current_link',
            provided_by=env.valid_envs)
    if migrate and restore_db:
        utils.abort('rollback cannot do both migrate and restore_db')
    if migrate:
        utils.abort("rollback: haven't worked out how to do migrate yet ...")

    _set_vcs_root_dir_timestamp()

    if version == 'last':
        # get the latest directory from prev_dir
        version_list = _get_list_of_versions()
        current_index = version_list.index(env.vcs_root_dir_timestamp)
        version = version_list[current_index - 1]
    # check version specified exists
    rollback_dir = path.join(env.server_project_home, version)
    if not files.exists(rollback_dir):
        utils.abort("Cannot rollback to version %s, it does not exist, use"
                    "list_versions to see versions available" % version)

    webserver_cmd("stop")
    # first make a db dump of the current state
    _dump_db_in_directory(env.vcs_root_dir)
    if migrate:
        # run the south migrations back to the old version
        # but how to work out what the old version is??
        pass
    if restore_db:
        # feed the dump file into mysql command
        with cd(rollback_dir):
            _tasks('load_dbdump')
    # change current link
    if files.exists(env.current_link):
        sudo_or_run('rm %s' % env.current_link)
    with cd(env.server_project_home):
        sudo_or_run('ln -s %s current' % version)
    webserver_cmd("start")


def local_test():
    """ run the django tests on the local machine """
    require('project_name', 'test_cmd')
    with cd(path.join("..", env.project_name)):
        local("python " + env.test_cmd, capture=False)


def remote_test():
    """ run the django tests remotely - staging only """
    require('django_dir', 'test_cmd', provided_by=env.valid_envs)
    if env.environment == 'production':
        utils.abort('do not run tests on the production environment')
    with cd(env.django_dir):
        sudo_or_run(_get_python() + env.test_cmd)


def version():
    """ return the deployed VCS revision and commit comments"""
    require('repo_type', 'vcs_root_dir', provided_by=env.valid_envs)
    if env.repo_type == "git":
        with cd(env.vcs_root_dir):
            sudo_or_run('git log | head -5')
    elif env.repo_type == "svn":
        _get_svn_user_and_pass()
        with cd(env.vcs_root_dir):
            with hide('running'):
                cmd = 'svn log --non-interactive --username %s --password %s | head -4' % \
                    (env.svnuser, env.svnpass)
                sudo_or_run(cmd)
    else:
        utils.abort('Unsupported repo type: %s' % (env.repo_type))


def _check_git_branch(revision):
    # cover the case where the revision (or commit ID) is passed on the
    # command line.  If it is, then skip the checking
    require('vcs_root_dir', provided_by=env.valid_envs)
    if revision:
        env.revision = revision
        return
    env.revision = None
    with cd(env.vcs_root_dir):
        with settings(warn_only=True):
            # get branch information
            server_branch = sudo_or_run('git rev-parse --abbrev-ref HEAD')
            server_commit = sudo_or_run('git rev-parse HEAD')
            local_branch = local('git rev-parse --abbrev-ref HEAD', capture=True)
            default_branch = env.default_branch.get(env.environment, 'master')
            server_git_branch_r = sudo_or_run('git branch --color=never -r')
            server_git_branch_r = server_git_branch_r.split('\n')
            server_branches = [b.split('/')[-1].strip() for b in
                               server_git_branch_r if 'HEAD' not in b]
            # it's possible the branch hasn't been pulled onto the server yet
            # so also check the remote branches that the local machine knows
            # about.  -r means that only branches that have been pushed
            # are included.  --remote would be nicer, but that is only
            # available in newer versions of git
            local_git_branch_r = local('git branch --color=never -r')
            local_git_branch_r = local_git_branch_r.split('\n')
            local_branches = [b.split('/')[-1].strip() for b in
                              local_git_branch_r if 'HEAD' not in b]
            # and now combine, deduplicate and sort the combined set of branches
            branches = sorted(list(set(server_branches + local_branches)))

        # if all branches are the same, just stick to this branch
        if server_branch == local_branch == default_branch:
            env.revision = server_branch
        else:
            if server_branch == 'HEAD':
                # not on a branch - just print a warning
                print 'The server git repository is not on a branch'

            print 'Branch mismatch found:'
            print '* %s is the default branch for this server' % default_branch
            if server_branch == 'HEAD':
                print '* %s is the commit checked out on the server.' % server_commit
            else:
                print '* %s is the branch currently checked out on the server' % server_branch
            print '* %s is the current branch of your local git repo' % local_branch
            print ''
            print 'Available branches are:'
            for branch in branches:
                print '* %s' % branch
            print ''
            escaped_branches = [re.escape(b) for b in branches]
            validate_branch = '^' + '|'.join(escaped_branches) + '$'

            env.revision = prompt('Which branch would you like to use on the server? (or hit Ctrl-C to exit)',
                    default=default_branch, validate=validate_branch)


def check_for_local_changes(revision):
    """ check if there are local changes on the remote server """
    require('repo_type', 'vcs_root_dir', provided_by=env.valid_envs)
    status_cmd = {
        'svn': 'svn status --quiet',
        'git': 'git status --short',
        'cvs': '#not worked out yet'
    }
    if env.repo_type == 'cvs':
        print "TODO: write CVS status command"
        return
    if files.exists(path.join(env.vcs_root_dir, "." + env.repo_type)):
        with cd(env.vcs_root_dir):
            status = sudo_or_run(status_cmd[env.repo_type])
            if status:
                print 'Found local changes on %s server' % env.environment
                print status
                cont = prompt('Would you like to continue with deployment? (yes/no)',
                        default='no', validate=r'^yes|no$')
                if cont == 'no':
                    utils.abort('Aborting deployment')
        if env.repo_type == 'git':
            _check_git_branch(revision)


def checkout_or_update(in_next=False, revision=None):
    """ checkout or update the project from version control.

    This command works with svn, git and cvs repositories.

    You can also specify a revision to checkout, as an argument."""
    require('next_dir', 'vcs_root_dir', 'repo_type', provided_by=env.valid_envs)
    checkout_fn = {
        'cvs': _checkout_or_update_cvs,
        'svn': _checkout_or_update_svn,
        'git': _checkout_or_update_git,
    }
    if in_next:
        vcs_root_dir = env.next_dir
    else:
        vcs_root_dir = env.vcs_root_dir
    if env.repo_type.lower() in checkout_fn:
        checkout_fn[env.repo_type](vcs_root_dir, revision)
    else:
        utils.abort('Unsupported VCS: %s' % env.repo_type.lower())


def _checkout_or_update_svn(vcs_root_dir, revision=None):
    require('server_project_home', 'repository', provided_by=env.valid_envs)
    # function to ask for svnuser and svnpass
    _get_svn_user_and_pass()
    # if the .svn directory exists, do an update, otherwise do
    # a checkout
    cmd = 'svn %s --non-interactive --no-auth-cache --username %s --password %s'
    if files.exists(path.join(vcs_root_dir, ".svn")):
        cmd = cmd % ('update', env.svnuser, env.svnpass)
        if revision:
            cmd += " --revision " + revision
        with cd(vcs_root_dir):
            with hide('running'):
                sudo_or_run(cmd)
    else:
        cmd = cmd + " %s %s"
        cmd = cmd % ('checkout', env.svnuser, env.svnpass, env.repository, vcs_root_dir)
        if revision:
            cmd += "@" + revision
        with cd(env.server_project_home):
            with hide('running'):
                sudo_or_run(cmd)


def _checkout_or_update_git(vcs_root_dir, revision=None):
    require('server_project_home', 'repository', provided_by=env.valid_envs)
    # if the .git directory exists, do an update, otherwise do
    # a clone
    if files.exists(path.join(vcs_root_dir, ".git")):
        with cd(vcs_root_dir):
            sudo_or_run('git remote rm origin')
            sudo_or_run('git remote add origin %s' % env.repository)
            # fetch now, merge later (if on branch)
            sudo_or_run('git fetch origin')

        if revision is None:
            revision = env.revision

        with cd(vcs_root_dir):
            stash_result = sudo_or_run('git stash')
            sudo_or_run('git checkout %s' % revision)
            # check if revision is a branch, and do a merge if it is
            with settings(warn_only=True):
                rev_is_branch = sudo_or_run('git branch -r | grep %s' % revision)
            # use old fabric style here to support Ubuntu 10.04
            if not rev_is_branch.failed:
                sudo_or_run('git merge origin/%s' % revision)
            # if we did a stash, now undo it
            if not stash_result.startswith("No local changes"):
                sudo_or_run('git stash pop')
    else:
        with cd(env.server_project_home):
            default_branch = env.default_branch.get(env.environment, 'master')
            sudo_or_run('git clone -b %s %s %s' %
                    (default_branch, env.repository, vcs_root_dir))

    if files.exists(path.join(vcs_root_dir, ".gitmodules")):
        with cd(vcs_root_dir):
            sudo_or_run('git submodule update --init')


def _checkout_or_update_cvs(vcs_root_dir, revision=None):
    require('server_project_home', 'repository', provided_by=env.valid_envs)
    if files.exists(vcs_root_dir):
        with cd(vcs_root_dir):
            sudo_or_run('CVS_RSH="ssh" cvs update -d -P')
    else:
        if 'cvs_user' in env:
            user_spec = env.cvs_user + "@"
        else:
            user_spec = ""

        with cd(env.server_project_home):
            cvs_options = '-d:%s:%s%s:%s' % (env.cvs_connection_type,
                                             user_spec,
                                             env.repository,
                                             env.repo_path)
            command_options = '-d %s' % vcs_root_dir

            if revision is not None:
                command_options += ' -r ' + revision

            sudo_or_run('%s cvs %s checkout %s %s' % (env.cvs_rsh, cvs_options,
                                                      command_options,
                                                      env.cvs_project))


def sudo_or_run(command):
    if env.use_sudo:
        # we want the first use of sudo to be for something where we don't
        # read the result - otherwise the result can include asking for the
        # password, or the first run message about "with great power ..."
        if not env.sudo_has_been_used:
            sudo("true")
            env.sudo_has_been_used = True
        return sudo(command)
    else:
        return run(command)


def create_deploy_virtualenv(in_next=False, full_rebuild=True):
    """ if using new style dye stuff, create the virtualenv to hold dye """
    require('deploy_dir', 'next_dir', provided_by=env.valid_envs)
    if in_next:
        bootstrap_path = path.join(env.next_dir, env.relative_deploy_dir,
                                   'bootstrap.py')
    else:
        bootstrap_path = path.join(env.deploy_dir, 'bootstrap.py')
    if full_rebuild:
        args = '--full-rebuild --quiet'
    else:
        args = '--quiet'
    sudo_or_run('%s %s %s' % (_get_python(), bootstrap_path, args))


def update_requirements(in_next=False):
    """ update external dependencies on remote host """
    create_deploy_virtualenv(in_next, full_rebuild=False)


def collect_static_files():
    """ collect static files in the 'static' directory """
    _tasks('collect_static')


def clean_db(revision=None):
    """ delete the entire database """
    if env.environment == 'production':
        utils.abort('do not delete the production database!!!')
    _tasks("clean_db")


def get_remote_dump(filename=None, local_filename=None, rsync=True):
    """ do a remote database dump and copy it to the local filesystem """
    # future enhancement, do a mysqldump --skip-extended-insert (one insert
    # per line) and then do rsync rather than get() - less data transferred on
    # however rsync might need ssh keys etc
    require('user', 'host', 'port', provided_by=env.valid_envs)
    delete_after = False
    if filename is None:
        filename = '/tmp/db_dump.sql'
    if local_filename is None:
        # set a default, but ensure we can write to it
        local_filename = './db_dump.sql'
        if not _local_is_file_writable(local_filename):
            # if we have to use /tmp, delete the file afterwards
            local_filename = '/tmp/db_dump.sql'
            delete_after = True
    else:
        # if the filename is specified, then don't change the name
        if not _local_is_file_writable(local_filename):
            raise Exception(
                'Cannot write to local dump file you specified: %s' % local_filename)
    if rsync:
        _tasks('dump_db:' + filename + ',for_rsync=true')
        local("rsync -vz -e 'ssh -p %s' %s@%s:%s %s" % (
            env.port, env.user, env.host, filename, local_filename))
    else:
        _tasks('dump_db:' + filename)
        get(filename, local_path=local_filename)
    sudo_or_run('rm ' + filename)
    return local_filename, delete_after


def get_remote_dump_and_load(filename=None, local_filename=None,
                             keep_dump=True, rsync=True):
    """ do a remote database dump, copy it to the local filesystem and then
    load it into the local database """
    require('local_tasks_bin', provided_by=env.valid_envs)
    local_filename, delete_after = get_remote_dump(
        filename=filename, local_filename=local_filename, rsync=rsync)
    local(env.local_tasks_bin + ' restore_db:' + local_filename)
    if delete_after or not keep_dump:
        local('rm ' + local_filename)


def update_db(force_use_migrations=False):
    """ create and/or update the database, do migrations etc """
    _tasks('update_db:force_use_migrations=%s' % force_use_migrations)


def setup_db_dumps():
    """ set up mysql database dumps """
    require('dump_dir', provided_by=env.valid_envs)
    _tasks('setup_db_dumps:' + env.dump_dir)


def touch_wsgi():
    """ touch wsgi file to trigger reload """
    require('vcs_root_dir', provided_by=env.valid_envs)
    wsgi_dir = path.join(env.vcs_root_dir, env.relative_wsgi_dir)
    sudo_or_run('touch ' + path.join(wsgi_dir, 'wsgi_handler.py'))


def rm_pyc_files(py_dir=None):
    """Remove all the old pyc files to prevent stale files being used"""
    require('django_dir', provided_by=env.valid_envs)
    if py_dir is None:
        py_dir = env.django_dir
    with settings(warn_only=True):
        with cd(py_dir):
            sudo_or_run('find . -type f -name \*.pyc -exec rm {} \\;')


def _delete_file(path):
    if files.exists(path):
        sudo_or_run('rm %s' % path)


def _link_files(source_file, target_path):
    if not files.exists(target_path):
        sudo_or_run('ln -s %s %s' % (source_file, target_path))


def link_webserver_conf(maintenance=False):
    """link the webserver conf file"""
    require('webserver', 'vcs_root_dir', provided_by=env.valid_envs)
    if env.webserver is None:
        return

    vcs_config_stub = path.join(env.vcs_root_dir, env.relative_webserver_dir,
                                env.environment)
    vcs_config_live = vcs_config_stub + '.conf'
    vcs_config_maintenance = vcs_config_stub + '-maintenance.conf'
    webserver_conf = _webserver_conf_path()

    if maintenance:
        _delete_file(webserver_conf)
        if not files.exists(vcs_config_maintenance):
            return
        _link_files(vcs_config_maintenance, webserver_conf)
    else:
        if not files.exists(vcs_config_live):
            utils.abort('No %s conf file found - expected %s' %
                    (env.webserver, vcs_config_live))
        _delete_file(webserver_conf)
        _link_files(vcs_config_live, webserver_conf)

    # debian has sites-available/sites-enabled split with links
    if _linux_type() == 'debian':
        webserver_conf_enabled = webserver_conf.replace('available', 'enabled')
        _link_files(webserver_conf, webserver_conf_enabled)
    webserver_configtest()


def _webserver_conf_path():
    require('webserver', 'project_name', provided_by=env.valid_envs)
    webserver_conf_dir = {
        'apache_redhat': '/etc/httpd/conf.d',
        'apache_debian': '/etc/apache2/sites-available',
    }
    key = env.webserver + '_' + _linux_type()
    if key in webserver_conf_dir:
        return path.join(webserver_conf_dir[key],
            '%s_%s.conf' % (env.project_name, env.environment))
    else:
        utils.abort('webserver %s is not supported (linux type %s)' %
                (env.webserver, _linux_type()))


def webserver_configtest():
    """ test webserver configuration """
    require('webserver', provided_by=env.valid_envs)
    tests = {
        'apache_redhat': '/usr/sbin/httpd -S',
        'apache_debian': '/usr/sbin/apache2ctl -S',
    }
    if env.webserver:
        key = env.webserver + '_' + _linux_type()
        if key in tests:
            sudo(tests[key])
        else:
            utils.abort('webserver %s is not supported (linux type %s)' %
                    (env.webserver, _linux_type()))


def webserver_reload():
    """ reload webserver on remote host """
    webserver_cmd('reload')


def webserver_restart():
    """ restart webserver on remote host """
    webserver_cmd('restart')


def webserver_cmd(cmd):
    """ run cmd against webserver init.d script """
    require('webserver', provided_by=env.valid_envs)
    cmd_strings = {
        'apache_redhat': '/etc/init.d/httpd',
        'apache_debian': '/etc/init.d/apache2',
    }
    if env.webserver:
        key = env.webserver + '_' + _linux_type()
        if key in cmd_strings:
            sudo(cmd_strings[key] + ' ' + cmd)
        else:
            utils.abort('webserver %s is not supported' % env.webserver)
