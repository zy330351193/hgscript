# !usr/bin/env python
# coding: utf-8
# author: WanCheng <zhaowcheng@163.com>

import paramiko
import time
from datetime import datetime


class Ssh(object):
    """
    SSH Client.
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
        return stdout.read().strip(), stderr.read().strip()

    def interact(self, commands,term='', timeout=30):
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



