# !usr/bin/env python
# coding: utf-8
import paramiko
import os
from datetime import datetime

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
            start = datetime.now()
            tout = ''
            while (datetime.now() - start).seconds < timeout:
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