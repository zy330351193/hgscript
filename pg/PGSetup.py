# !/usr/bin/env python
# coding=utf-8
'''
此模块主要用于pg安装编译
'''
import os

from method.RemoteConnect import ssh_connectionServer,ftp_connectionServer,ssh_connectionServer_2
from configuration.pg_parameter.parameter import setup

def send_package(local_file_path,remote_ip,username='root',passwd=''):
    '''
    此方法用于传包,将包传到/root下
    '''
    file=os.path.basename(local_file_path)
    print('开始传包')
    ftp_connectionServer(local_file_path,'/root/'+file,2,remote_ip,username,passwd)
    print('传包成功')
    print('开始解压')

    sf=ssh_connectionServer_2(remote_ip,username,passwd)
    sf.exec_command('tar -zxvf %s'%file,timeout=180)

def compile(ip,passwd,username='root'):
    '''
    此方法用于编译
    '''
    pass

send_package(setup['local_package_path'],setup['remote_ip'],'root',setup['root_password'])