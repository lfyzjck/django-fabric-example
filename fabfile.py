from fabric.api import *
from fabric.contrib.files import exists
import os
# globals
env.project_name = 'bookshelf'
# environments
def localhost():
    "Use the local virtual server"
    env.hosts = ['xx.xx.xx.x']
    # env.path = os.path.abspath(os.path.dirname(__file__))
    env.path = '/var/www/%(project_name)s' % env
    env.user = 'root'
def webserver():
    "Use the actual webserver"
    env.hosts = ['git.mysite.com']
    env.user = 'root'
    env.path = '/var/www/%(project_name)s' % env
# tasks
def test():
    "Run the test suite and bail out if it fails"
    local("cd $(project_name); python manage.py test", fail="abort")
def setup_163_rpm():
    sudo('mv /etc/yum.repos.d/CentOS-Base.repo /etc/yum.repos.d/CentOS-Base.repo.backup')
    sudo('wget http://mirrors.163.com/.help/CentOS6-Base-163.repo')
    sudo('mv CentOS6-Base-163.repo /etc/yum.repos.d')
    sudo('yum makecache')
def setup_epel_rpm():
    sudo('wget http://dl.fedoraproject.org/pub/epel/6/x86_64/epel-release-6-8.noarch.rpm')
    sudo('rpm -Uvh epel-release-6*.rpm')
    sudo('rm -f epel-release-6-8.noarch.rpm')
    sudo('yum makecache')
def setup_python_env():
    sudo('yum install -y python-setuptools python-pip python-devel')
    sudo('easy_install uwsgi')
    sudo('easy_install -U distribute')
def setup_nginx():
    sudo('yum install -y nginx')
    sudo('chkconfig --add nginx')
    sudo('chkconfig --level 345 nginx on')
def setup_mysql():
    sudo('yum install -y mysql mysql-devel')
def setup():
    """
    Setup a fresh virtualenv as well as a few useful directories, then run
    a full deployment
    """
    require('hosts', provided_by=[localhost])
    require('path')
    setup_nginx()
    setup_mysql()
    setup_python_env()
    # we want rid of the defult apache env
    # sudo('cd /etc/apache2/sites-available/; a2dissite default;')
    # run('mkdir -p $(path); cd $(path); virtualenv .;')
    # run('cd $(path); mkdir releases; mkdir shared; mkdir packages;', fail='ignore')
    # deploy()

def deploy():
    """
    Deploy the latest version of the site to the servers, install any
    required third party modules, install the virtual host and 
    then restart the webserver
    """
    require('hosts', provided_by=[localhost,webserver])
    require('path')
    import time
    env.release = time.strftime('%Y%m%d%H%M%S')
    upload_tar_from_git()
    #install_requirements()
    # install_site()
    symlink_current_release()
    # project_prepare()
    # restart_webserver()
def deploy_version(version):
    "Specify a specific version to be made live"
    require('hosts', provided_by=[localhost,webserver])
    require('path')
    env.version = version
    with cd(env.path):
        run('rm releases/previous; mv releases/current releases/previous;', pty=True)
        run('ln -s %(version)s releases/current' % env, pty=True)
    project_prepare()
    restart_webserver()
def rollback():
    """
    Limited rollback capability. Simple loads the previously current
    version of the code. Rolling back again will swap between the two.
    """
    require('hosts', provided_by=[localhost])
    require('path')
    with cd(env.path):
        run('mv releases/current releases/_previous;', pty=True)
        run('mv releases/previous releases/current;', pty=True)
        run('mv releases/_previous releases/previous;', pty=True)
    project_prepare()
    restart_webserver()     
# Helpers. These are called by other functions rather than directly
def upload_tar_from_git():
    "Create an archive from the current Git master branch and upload it"
    require('release', provided_by=[deploy, setup])
    local('git archive --format=tar master | gzip > %(release)s.tar.gz' % env)
    run('mkdir -p %(path)s/releases/%(release)s' % env, pty=True)
    run('mkdir -p %(path)s/packages' % env, pty=True)
    put('%(release)s.tar.gz' % env, '%(path)s/packages/' % env)
    run('cd %(path)s/releases/%(release)s && tar zxf ../../packages/%(release)s.tar.gz' % env, pty=True)
    local('rm %(release)s.tar.gz' % env)
def install_site():
    "Add the virtualhost file to apache"
    require('release', provided_by=[deploy, setup])
    sudo('cd $(path)/releases/$(release); cp $(project_name)$(virtualhost_path)$(project_name) /etc/apache2/sites-available/')
    sudo('cd /etc/apache2/sites-available/; a2ensite $(project_name)') 
def install_requirements():
    "Install the required packages from the requirements file using pip"
    require('release', provided_by=[deploy, setup])
    run('cd %(path)s; python-pip install -r ./releases/%(release)s/requirements.txt' % env, pty=True)
def symlink_current_release():
    "Symlink our current release"
    require('release', provided_by=[deploy, setup])
    with cd(env.path):
        if not exists('releases/current'):
            run('mkdir releases/current')
        run('rm -rf releases/previous; mv releases/current releases/previous;')
        run('ln -s %(release)s releases/current' % env)
def restart_webserver():
    "Restart the web server"
    sudo('uwsgi --reload /var/run/%(project_name)s.pid' % env)
    sudo('nginx -s reload')

def celery_reload():
    sudo('celery multi restart bookshelf')