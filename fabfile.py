from fabric.api import local, run, cd, shell_env, quiet, env, abort, prompt
from fabric.colors import blue, red, yellow, green
from myimagebot import config
import os
import re
import inspect


env.hosts = ['xoul@xoul.kr']
# env.passwords = {
#     env.hosts[0]: 'znptmxm51!'
# }


"""
Local Commands
"""


def _g(f):
    """Global decorator.

    1. Wraps environment variables.
    2. Wraps quiet.
    """
    def decorator(*args, **kwargs):
        env_vars = dict()
        env_vars['ROOT'] = os.path.abspath(os.path.join(__file__, '..', '..'))
        env_vars['VAR'] = os.path.join(env_vars['ROOT'], 'var')
        env_vars['CONF'] = os.path.join(env_vars['ROOT'], 'myimagebot', 'conf')
        env_vars['VENV'] = os.path.join(env_vars['ROOT'], 'venv')

        with shell_env(**env_vars):
            if 'env_vars' in inspect.getargspec(f)[0]:
                kwargs['env_vars'] = env_vars
            with quiet():
                return f(*args, **kwargs)
    return decorator


def _running():
    """Returns whether uwsgi processes are running."""
    r = local('ps aux | grep uwsgi.*myimagebot', capture=True).stdout
    return '.ini' in r


def _pid():
    """Returns PID if PID file exists or returns `None`."""
    pid = local('cat $VAR/run/myimagebot.pid', capture=True).stdout
    if pid:
        return pid
    return None


def _kill():
    local("ps aux | grep uwsgi.*myimagebot | awk '{print $2}' | "
          "xargs kill -9 2>/dev/null")


def _abort(message):
    abort(red(message))


@_g
def _conf_exists(env_vars):
    """Returns `False` if there is no file in `$CONF` directory."""
    conf_path = os.path.join(env_vars['CONF'], 'gen')
    files = [f for f in os.listdir(conf_path) if f[0] != '.']
    return not not files


@_g
def conf(env_vars):
    """Compiles configurations"""

    print blue("* Generating 'conf/gen'..."),
    local('[ -e $CONF/gen ] && rm -r $CONF/gen')
    local('cp -R $CONF/src $CONF/gen')
    print blue('Done')

    dir_gen = os.path.join(env_vars['CONF'], 'gen')
    for filename in os.listdir(dir_gen):
        if filename[0] == '.':
            continue
        print blue("* Compiling '%s'..." % filename),
        f = open(os.path.join(dir_gen, filename), 'r+')
        pattern = r'\{%\s*(.*)\s*%\}'
        content = f.read()
        repl = lambda match: env_vars[match.groups(0)[0].strip()]
        content = re.sub(pattern, repl, content)
        f.seek(0)
        f.write(content)
        f.close()
        print blue('Done')


@_g
def nginx():
    """Configure nginx."""
    source = '$CONF/gen/myimagebot.nginx.conf'
    target = '/etc/nginx/sites-enabled/myimagebot.nginx.conf'

    print blue("* Creating symbolic link..."),
    local('[ -e %s ] && sudo rm %s' % (target, target))
    local('sudo ln -s %s %s' % (source, target))
    print blue('Done')

    print blue("* Reloading nginx..."),
    local('sudo service nginx reload')
    print blue('Done')


@_g
def status():
    if _running():
        if _pid():
            print blue('* MyImageBot is running')
        else:
            print blue('* MyImageBot is running, but has no PID file.')
    else:
        if _pid():
            print yellow('* MyImageBot is not running, but has PID file.')
        else:
            print yellow('* MyImageBot is not running')


@_g
def start(env_vars):
    if _running():
        _kill()

    if not _conf_exists():
        conf()

    cmd = 'uwsgi $CONF/gen/myimagebot.ini --enable-threads'
    try:
        if config.DEBUG:
            cmd += ' --catch-exceptions'
            print green("*** DEBUG MODE ENABLED ***")
    except:
        pass

    print blue("* Starting MyImageBot..."),
    rv = local(cmd, capture=True)
    if rv.succeeded:
        print blue("Done")
    else:
        print red("Failed")
        _abort(rv.stderr)


@_g
def stop():
    if _running():
        if _pid():
            print blue("* Stopping..."),
            if local('uwsgi --stop $VAR/run/myimagebot.pid').succeeded and\
               local('rm $VAR/run/myimagebot.pid').succeeded:
                print blue('Done')
            else:
                print red('Failed')
        else:
            print blue("* MyImageBot is running, but has no PID file. "
                       "Killing...")
            _kill()
            print blue('Done')
    else:
        if _pid():
            print blue("* MyImageBot is not running, but has PID file. "
                       "Removing..."),
            if local('rm $VAR/run/myimagebot.pid').succeeded:
                print blue('Done')
            else:
                print red('Failed')
        else:
            print yellow("* MyImageBot is not running.")


@_g
def reload():
    if _running():
        if _pid():
            cmd = 'uwsgi --reload $VAR/run/myimagebot.pid'
            try:
                if config.DEBUG:
                    cmd += ' --catch-exceptions'
                    print green("*** DEBUG MODE ENABLED ***")
            except:
                pass
            print blue("* Reloading..."),
            local(cmd)
            print blue('Done')
        else:
            _abort("MyImageBot running, but has no PID file. "
                   "Use 'start' instead.")
    else:
        if _pid():
            _abort("MyImageBot is not running, but has PID file. "
                   "Use 'start' instead.")
        else:
            _abort("MyImageBot is not running.")


@_g
def restart():
    stop()
    start()


@_g
def start_celery(env_vars):
    print blue('* Starting celery...'),
    rv = local('celery multi start w1 -A myimagebot.tasks.celery '
               '--logfile=$VAR/log/%%N.log '
               '--pidfile=$VAR/run/%%N.pid', capture=True)
    if rv.succeeded:
        print blue('Done')
    else:
        print red('Failed')
        _abort(rv.stderr)


@_g
def stop_celery(env_vars):
    print blue('* Stopping celery...'),
    rv = local('celery multi stop w1 --pidfile=$VAR/run/%%N.pid')
    if rv.succeeded:
        print blue('Done')
    else:
        print red('Failed')
        _abort(rv.stderr)


@_g
def restart_celery():
    print blue('* Restarting celery...'),
    rv = local('celery multi restart w1 -A myimagebot.tasks.celery '
               '--logfile=$VAR/log/%%N.log '
               '--pidfile=$VAR/run/%%N.pid')
    if rv.succeeded:
        print blue('Done')
    else:
        print red('Failed')
        _abort(rv.stderr)


@_g
def log(type='uwsgi'):
    """Open a log file.

    :param type: Log type. 'uwsgi'(default), 'nginx.access', 'nginx.error'
    """
    if type == 'uwsgi':
        local('open $VAR/log/myimagebot.log')
    elif type == 'nginx.access':
        local('open $VAR/log/nginx/myimagebot.access.log')
    elif type == 'nginx.error':
        local('open $VAR/log/nginx/myimagebot.error.log')


"""
Deploy Command
"""


def deploy():
    """with quiet():
        rv = local('git status', capture=True).stdout.strip()
        if 'nothing to commit' not in rv:
            _abort('Commit all changes before deployment.')
        print blue('* Updating git branch `deploy`...'),
        branch = local('git rev-parse --abbrev-ref HEAD', capture=True).stdout
        local('git checkout deploy')
        local('git rebase %s' % branch)
        local('git push')
        local('git checkout %s' % branch)
        print blue('Done')"""

    run('git config --global credential.helper "cache --timeout=3600"')
    rv = run('[ -d myimagebot ] && (cd myimagebot && git checkout master && '
             'git stash save --keep-index && git pull --ff) || '
             'git clone https://github.com/jaechang/myimagebot.git')
    if rv.failed:
        _abort(rv.stderr)

    # check `venv` directory exists
    run('[ -d venv ] || virtualenv venv')
    run('. venv/bin/activate')

    # check `var` directory exists
    run('[ -d var ]|| mkdir var var/log var/log/nginx var/run var/upload')

    # Path for Booost.
    with shell_env(LD_LIBRARY_PATH='/opt/local/lib'):
        with cd('myimagebot'):
            #run('pip install -r requirements.txt')
            rv = run('fab conf nginx stop start')
            if rv.failed:
                _abort(rv.stderr)


"""
Remote Commands
"""


def remote(cmd):
    """Run local commands from remote.

    Usage: $fab remote:start
    """
    # Path for Booost.
    with shell_env(LD_LIBRARY_PATH='/opt/local/lib'):
        with cd('myimagebot'):
            run('fab ' + cmd)

r = remote
