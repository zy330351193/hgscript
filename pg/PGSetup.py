# !/usr/bin/env python
# coding=utf-8
'''
此模块主要用于pg安装编译
'''
import os

from method.RemoteConnect import ssh_connectionServer, ftp_connectionServer, Ssh
from configuration.pg_parameter.parameter import setup
from method.RemoteConnect import check_exec_command
import re
from multiprocessing import Process


def send_package(local_file_path, remote_ip, username='root', passwd=''):
    '''
    此方法用于传包,将包传到/root下,并解压
    local_file_path:本地文件路径(带文件名)
    remote_ip:远端IP，需连接的IP
    username:远端连接名
    passwd:远端连接密码
    '''
    res = re.search(r'(.*)\.tar', os.path.basename(local_file_path))
    file = res.group(1)
    sf = ssh_connectionServer(remote_ip, username, passwd)
    _, stdout, stderr = sf.exec_command('ls /root')
    if re.search('%s' % file, stdout.read().decode()):
        print('包已存在并解压')
    else:
        file = os.path.basename(local_file_path)
        print('%s开始传包......' % remote_ip)
        ftp_connectionServer(local_file_path, '/root/' + file, 2, remote_ip, username, passwd)
        print('%s传包成功!!!!!!' % remote_ip)
        print('%s开始解压......' % remote_ip)

        res = sf.exec_command('tar -zxvf %s' % file, timeout=180)
        check_exec_command(res, 'INSTALL', '%s解压完成!!!!!!' % remote_ip, '%s解压失败!!!!!!' % remote_ip)
        print('%s删除压缩包'%remote_ip)
        sf.exec_command('rm -rf %s'%file)
    sf.close()


def compile(local_file_path, remote_ip, username='root', passwd=''):
    '''
    此方法用于编译pg源码包
    local_file_path:本地pg源码包文件路径(带文件名)
    remote_ip:远端IP，需连接的IP
    username:远端连接名
    passwd:远端连接密码
    '''
    # 因上传的包解压后无文件格式后后缀，故先将文件格式后缀去掉，便于找到文件
    res = re.search(r'(.*)\.tar', os.path.basename(local_file_path))
    file = res.group(1)
    sf = ssh_connectionServer(remote_ip, username, passwd)
    print('%s开始configure配置......' % remote_ip)
    stdin, stdout, stderr = sf.exec_command(
        'cd {0};./configure --prefix={1} --enable-nls="zh_CN zh_TW"'.format(file, setup['pgpath']))
    res = stdout.read().decode() + stderr.read().decode()
    if re.search('configure\s*:\s*error', res):
        raise Exception('%s配置出错!!!!!!\n' % remote_ip + res)
    print("%s配置结束!!!!!!\n" % remote_ip + '%s开始编译......' % remote_ip)
    res = sf.exec_command('cd {0};gmake world -j4'.format(file), timeout=360)
    check_exec_command(res, 'successfully.*Ready to install', '%s编译成功' % remote_ip, '%s编译失败' % remote_ip)
    print('%s编译结束!!!!!!\n' % remote_ip + '%s开始安装......' % remote_ip)
    res = sf.exec_command('cd {0};gmake install-world'.format(file), timeout=360)
    check_exec_command(res, 'installation complete', '%s安装成功' % remote_ip, '%s安装失败' % remote_ip)
    print('%s安装结束!!!!!!' % remote_ip)
    sf.close()


def compile_pgpool(local_file_path, remote_ip, username='root', passwd=''):
    '''
    此方法用于编译pg源码包
    local_file_path:本地pgpool包文件路径(带文件名)
    remote_ip:远端IP，需连接的IP
    username:远端连接名
    passwd:远端连接密码
    '''
    # 因上传的包解压后无文件格式后后缀，故先将文件格式后缀去掉，便于找到文件
    res = re.search(r'(.*)\.tar', os.path.basename(local_file_path))
    file = res.group(1)
    sf = ssh_connectionServer(remote_ip, username, passwd)
    print('%s开始configure配置pgpool......' % remote_ip)
    stdin, stdout, stderr = sf.exec_command(
        'cd {0};./configure --prefix={1} --with-pgsql={2} '.format(
            file, setup['pgpoolpath'], setup['pgpath']))
    res = stdout.read().decode() + stderr.read().decode()

    if re.search('configure\s*:\s*error', res):
        raise Exception('%s配置pgpool出错!!!!!!' % remote_ip + '\n' + res)
    print("%s配置pgpool结束!!!!!!\n" % remote_ip + '%s开始编译pgpool......' % remote_ip)
    res = sf.exec_command('cd {0};make'.format(file), timeout=360)
    check_exec_command(res, 'make  all-am', '%s编译pgpool成功' % remote_ip, '%s编译pgpool失败' % remote_ip)
    print('%s编译pgpool结束!!!!!!\n' % remote_ip + '%s开始安装pgpool......' % remote_ip)
    res = sf.exec_command('cd {0};make install'.format(file), timeout=360)
    check_exec_command(res, 'Making install in include', '%s安装pgpool成功' % remote_ip, '%s安装pgpool失败' % remote_ip)
    print('%s编译pgpool扩展......' % remote_ip)
    res = sf.exec_command('cd {0}/src/sql/pgpool-recovery;export PATH={1}/bin:$PATH;make'.format(file, setup['pgpath']),
                          timeout=360)
    check_exec_command(res, 'pgpool-recovery.o|Nothing to be done', '%spgpool扩展编译成功' % remote_ip,
                       '%spgpool扩展编译失败' % remote_ip)
    res = sf.exec_command(
        'cd {0}/src/sql/pgpool-recovery;export PATH={1}/bin:$PATH;make install'.format(file, setup['pgpath']),
        timeout=360)

    check_exec_command(res, 'mkdir', '%s安装pgpool扩展成功' % remote_ip, '%s安装pgpool扩展失败' % remote_ip)

    print('%s安装pgpool结束!!!!!!' % remote_ip)
    sf.close()


def configure(remote_ip, username, passwd):
    '''
    此方法对安装后的包进行配置，包括创建用户，设置环境变量等
    remote_ip:远端IP，需连接的IP
    username:远端连接名
    passwd:远端连接密码
    '''
    sf = Ssh(remote_ip)
    # 创建用户和密码
    print('创建postgres用户')
    sf.connect(username, passwd)
    sf.execute('groupadd postgres')
    sf.execute('useradd postgres -g postgres')
    print('修改密码......')
    sf.interact([('passwd postgres', 'New password:'),
                 ('%s' % setup['postgrespasswd'], 'Retype new password:'),
                 ('%s' % setup['postgrespasswd'], '#')], timeout=5)
    print('修改文件夹权限......')
    sf.execute('chown postgres:postgres -R %s' % setup['pgpath'])
    # 若有pgpool参数,添加pgpool环境变量
    if setup['pgpoolpath']:
        res = sf.execute('cat ~/.bash_profile')
        if not re.search('%s' % setup['pgpoolpath'], res):
            print('添加pgpool环境变量')
            sf.execute('echo "export PATH={0}/bin:\$PATH" >> ~/.bash_profile'.format(setup['pgpoolpath']))
            sf.execute('source ~/.bash_profile')
    # 用postgres用户登录修改环境变量配置
    sf = ssh_connectionServer(remote_ip, setup['pgusername'], setup['postgrespasswd'])
    # 若环境变量中无所需变量，则加入环境变量中
    _, stdout, stderr = sf.exec_command('cat ~/.bash_profile')
    res = stdout.read().decode()
    if not re.search('export PGHOME', res):
        print('添加环境变量')
        sf.exec_command('echo "export PGHOME=%s" >> ~/.bash_profile' % setup['pgpath'])
        sf.exec_command('echo "export PGDATA=%s/data" >> ~/.bash_profile' % setup['pgpath'])
        sf.exec_command('echo "export PATH=\$PGHOME/bin:\$PATH:\$HOME/bin" >> ~/.bash_profile')
        sf.exec_command('echo "export LD_LIBRARY_PATH=\$PGHOME/lib:\$LD_LIBRARY_PATH" >> ~/.bash_profile')
        sf.exec_command('source ~/.bash_profile')
    sf.close()


def main(remote_ip, username, passwd):
    '''
    主函数，确定哪些方法需要运行
    remote_ip:远端IP，需连接的IP
    username:远端连接名
    passwd:远端连接密码
    '''
    send_package(setup['local_package_path0'], remote_ip, username, passwd)
    compile(setup['local_package_path0'], remote_ip, username, passwd)
    configure(remote_ip, username, passwd)
    # 如果有pgpool参数则一起传包，编译
    if setup['local_package_path1']:
        send_package(setup['local_package_path1'], remote_ip, username, passwd)
        compile_pgpool(setup['local_package_path1'], remote_ip, username, passwd)


if __name__ == '__main__':
    jobs = []
    for remote_ip in [setup['remote_ip_0'], setup['remote_ip_1'], setup['remote_ip_2']]:
        if remote_ip:
            p = Process(target=main,
                        args=(remote_ip, 'root', setup['root_password']))

            p.start()
            jobs.append(p)
    for _ in jobs:
        p.join()
