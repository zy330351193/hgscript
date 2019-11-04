# !usr/bin/env python
# coding: utf-8
import paramiko
import os
import re
import time
# from paramiko.client import SSHClient

import datetime
from method.Collect_Log import collect_logger

def ssh_connectionServer(*server):
    '''创建ssh连接,返回连接对象
    *server参数接收由连接信息组成的元组，即server=(ip,username,passwd)
    '''
    try:
        # 创建SSH对象
        sf = paramiko.SSHClient()
        # 允许连接不在know_hosts文件中的主机
        sf.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # 连接服务器
        sf.connect(hostname=server[0], port=22, username=server[1],
                   password=server[2])
    except Exception as e:
        print(server[0], e)
    return sf

def check_exec_command(result, expect, describe_pass='符合预期', describe_fail='不符合预期'):
    '''此方法用于验证ssh_connectionServer中exec_command方法返回的结果是否符合预期
       result：接收exec_command的返回值
       expect:期望返回值中包含的字符串，多种期望可用 | 隔开
       describe_fail:对不符合预期场景进行描述
       describe_pass:对预期结果进行描述
    '''
    stdin, stdout, stderr = result
    res, err = stdout.read(), stderr.read()
    result = res + err
    if not re.search(expect, result.decode()):
        raise Exception(describe_fail+',执行结果为:\n'+result.decode())
    else:
        print(describe_pass)

def ftp_connectionServer(local_file, remote_file, ftpType, *server):
    '''创建ftp对象，用于上传下载文件
    参数含义：
    local_file:本地文件路径
    remote_file:远端文件路径
    ftpType：选择传输类型，ftpType=1 单个文件从其他服务器向本地下载；ftpType=2 单个文件向服务器上传；
    *server参数接收由连接信息组成的元组，即server=(ip,username,passwd)
    '''
    try:
        # 创建ftp对象
        sf = paramiko.Transport(server[0], 22)
        sf.connect(username=server[1], password=server[2])
        sftp = paramiko.SFTPClient.from_transport(sf)
    except Exception as e:
        print(server[0], e)
        return False

    local_path = os.path.dirname(local_file)
    if ftpType == 1:
        if not os.path.exists(local_path):
            os.makedirs(local_path)
        sftp.get(remote_file, local_file)
        sf.close()
    elif ftpType == 2:
        sftp.put(local_file, remote_file)
        sf.close()
    else:
        raise Exception('未选择传输模式')

class Ssh(object):
    """
    SSH Client.
    该类主要封装了可以进行交互的方法
    """

    def __init__(self, host, port=22):
        """
        Constructor.
        :param host: ip or hostname.
        :param port: ssh port.
        """
        self.host = host
        self.port = port
        self.ssh = paramiko.SSHClient()

    def connect(self, username, password):
        """
        SSH connect to remote host.
        :param username: Login username.
        :param password: Login password.
        """
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(hostname=self.host,
                         port=self.port,
                         username=username,
                         password=password)

    def execute(self, command, timeout=30):
        """
        Execute a command.
        :param command: Command string.
        :param timeout: Timeout.
        :return: stdout and stderr
        """
        _, stdout, stderr = self.ssh.exec_command(command, timeout=timeout)
        return stdout.read().strip().decode()+ stderr.read().strip().decode()

    def interact(self, commands, term='', timeout=5):
        """
        Execute multiple interactive commands.
        Commands format:
        [('ssh 192.168.1.100', '(yes/no)'),
        ('yes', 'Password:'),
        ('password', '#')]
        :param commands: Commands list.
        :param timeout: Timeout.
        :return: Output string.
        """
        chan = self.ssh.invoke_shell(term='', width=999, height=999)
        out = ''
        for cmd, expect in commands:
            chan.send(cmd + '\n')
            start = datetime.datetime.now()
            tout = ''
            while (datetime.datetime.now() - start).seconds < timeout:
                if chan.recv_ready():
                    tout += str(chan.recv(1024 * 10))
                    if tout.find(expect) > -1:
                        break
                time.sleep(0.5)
            else:
                raise Exception(
                    "Expect '%s' timeout(%ss) while Send '%s':\n%s" %
                    (expect, timeout, cmd, out))
            # append out
            out += tout
        return out



# class SSHClient_2(SSHClient):
#     '''重写类方法，因为有的exec_command需要接收参数才能执行，目前不清楚原因,将其参数接收加入日志中'''
#
#     def exec_command(
#         self,
#         command,
#         bufsize=-1,
#         timeout=None,
#         get_pty=False,
#         environment=None,
#     ):
#         chan = self._transport.open_session(timeout=timeout)
#         if get_pty:
#             chan.get_pty()
#         chan.settimeout(timeout)
#         if environment:
#             chan.update_environment(environment)
#         chan.exec_command(command)
#         stdin = chan.makefile_stdin("wb", bufsize)
#         stdout = chan.makefile("r", bufsize)
#         stderr = chan.makefile_stderr("r", bufsize)
#         print('+++++++++++++++++++++++++++++++++++++++++++\n'+
#               'cmd:'+command+'\n'+
#               '+++++++++++++++++++++++++++++++++++++++++++\n'+
#               stdout.read().decode(),stderr.read().decode()+'\n'
#               '+++++++++++++++++++++++++++++++++++++++++++')
#         return stdin, stdout, stderr
#
# def ssh_connectionServer_2(*server):
#     '''创建SSHClient_2连接对象,返回连接对象
#     *server参数接收由连接信息组成的元组，即server=(ip,username,passwd)
#     '''
#     try:
#         # 创建SSH对象
#         sf = SSHClient_2()
#         # 允许连接不在know_hosts文件中的主机
#         sf.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#         # 连接服务器
#         sf.connect(hostname=server[0], port=22, username=server[1],
#                    password=server[2])
#     except Exception as e:
#         print(server[0], e)
#     return sf