# !/usr/bin/env python
# coding=utf-8
from pprint import pprint
import paramiko
import multiprocessing
from parameter import parameters
import psycopg2
import re
import time


class PgpoolConfigure():
    def __init__(self, primary_node_ip, standby01_node_ip, standby02_node_ip, pgpath, pgpoolpath,
                 delegate_ip
                 ):
        self.primary_node = primary_node_ip
        self.standby01_node = standby01_node_ip
        self.standby02_node = standby02_node_ip
        self.pgpath = pgpath
        self.pgpoolpath = pgpoolpath
        self.delegate_ip = delegate_ip

    def ssh_connectionServer(self, *server):
        '''创建ssh连接,返回连接对象'''
        try:
            # 创建SSH对象
            sf = paramiko.SSHClient()
            # 允许连接不在know_hosts文件中的主机
            sf.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # 连接服务器
            sf.connect(hostname=server[0], port=22, username=server[1],
                       password=server[2])

            # stdin, stdout, stderr = sf.exec_command('cd /opt;ls')
            # result = stdout.read()
            # print(result)
        except Exception as e:
            print(server[0], e)
        return sf

    def basic_setting(self, *server):
        '''此方法用于改一些基础配置，如关闭防火墙，节点互信等'''
        sf = self.ssh_connectionServer(*server)

        # 关闭防火墙
        sf.exec_command('systemctl stop firewalld.service')
        sf.exec_command('service firewalld stop')
        sf.exec_command('systemctl disable firewalld.service')


        # 此步操作还未验证是否可行！！！！！！！！！！！！！！！！
        sf.exec_command('ssh-keygen -t rsa')
        sf.exec_command('ssh-copy-id -i  .ssh/id_rsa.pub root@192.168.222.142')
        # !!!!!!!!!!!!!!!!!!!!!!!!

        sf.exec_command(r'export PATH={0}/bin:{1}/bin:$PATH'.format(self.pgpath, self.pgpoolpath))
        sf.exec_command('source /etc/profile')
        # 创建所需文件，wal归档文件夹后面方法单独创建
        sf.exec_command('chmod 777 %s' % self.pgpath)
        sf.exec_command('mkdir {0}/log/ && touch {0}/log/pgpool.log'.format(self.pgpoolpath))
        sf.exec_command("echo 'localhost:9898:pgpool:pgpool' > ~/.pcppass")
        sf.exec_command("chmod 600 ~/.pcppass")
        sf.close()

    def basic_setting_by_dbuser(self, *server):
        sf = self.ssh_connectionServer(*server)
        sf.exec_command('echo "{0}:5432:replication:repl:{1}" >> ~/.pgpass'.format(parameters['primary_node_ip'],
                                                                                   parameters['dbpasswd']))
        sf.exec_command('echo "{0}:5432:replication:repl:{1}" >> ~/.pgpass'.format(parameters['standby01_node_ip'],
                                                                                   parameters['dbpasswd']))
        sf.exec_command('echo "{0}:5432:replication:repl:{1}" >> ~/.pgpass'.format(parameters['standby02_node_ip'],
                                                                                   parameters['dbpasswd']))
        sf.exec_command('chmod 600 ~/.pgpass')

        sf.close()

    def check_data_status(self, *server):
        '''此方检查数据库是否开启,*server=(ip,dbusername,dbpasswd)'''

        sf = self.ssh_connectionServer(*server)
        # 初始化数据库,如果不属于以下两种匹配类型则初始化是失败的
        res = sf.exec_command(
            'export LD_LIBRARY_PATH={0}/lib:$LD_LIBRARY_PATH;{0}/bin/initdb -D {0}/data'.format(self.pgpath),
            timeout=15)
        check_exec_command(res, 'exists but is not empty|Success. You can now start the database server using',
                           '%s数据库初始化成功' % server[0], '%s数据库初始化失败' % server[0])

        # 启动数据库,判断数据库是否开启
        sf.exec_command(
            r'export PATH=$PATH:$PGHOME/bin:{0}/bin;export LD_LIBRARY_PATH={0}/lib:$LD_LIBRARY_PATH;{0}/bin/pg_ctl start -D {0}/data'.format(
                self.pgpath))
        time.sleep(1)
        res = sf.exec_command(
            'export LD_LIBRARY_PATH={0}/lib:$LD_LIBRARY_PATH;{0}/bin/pg_isready -d {0}/data'.format(self.pgpath))
        check_exec_command(res, 'accepting connections', '%s数据库启动成功' % server[0], '%s数据库启动失败' % server[0])
        # 主库修改postgres密码，创建流复制用户
        res = sf.exec_command(
            '''export LD_LIBRARY_PATH={0}/lib:$LD_LIBRARY_PATH;{0}/bin/psql -c "ALTER USER postgres WITH PASSWORD '123456'";'''.format(
                self.pgpath))
        check_exec_command(res, 'ALTER ROLE', '%s修改用户密码成功' % server[0], '%s修改用户密码失败' % server[0])

        res = sf.exec_command(
            '''export LD_LIBRARY_PATH={0}/lib:$LD_LIBRARY_PATH;{0}/bin/psql -c "CREATE ROLE pgpool WITH PASSWORD '123456' LOGIN;";'''.format(
                self.pgpath))
        check_exec_command(res, ' role "pgpool" already exists|CREATE ROLE', '%s创建pgpool角色成功' % server[0],
                           '%s创建pgpool角色失败' % server[0])

        res = sf.exec_command(
            '''export LD_LIBRARY_PATH={0}/lib:$LD_LIBRARY_PATH;{0}/bin/psql -c "CREATE ROLE repl WITH PASSWORD '123456' REPLICATION LOGIN";'''.format(
                self.pgpath))
        check_exec_command(res, 'role "repl" already exists|CREATE ROLE', '%s创建流复制角色成功' % server[0],
                           '%s创建角色失败' % server[0])
        sf.close()

    def change_pgpool_conf_parameters(self, *server, **three_ip):
        '''此方法用于修改pgpool.conf文件参数和pool_hba.conf文件
        *server接收参数为连接的服务器ip,连接的用户名，连接密码组成的元组
        '''

        sf = self.ssh_connectionServer(*server)
        # 拷贝pgpool.conf文件
        path_pgpool_conf = self.pgpoolpath + '/etc'
        sf.exec_command('cd {0};cp pgpool.conf.sample pgpool.conf '.format(path_pgpool_conf))
        pgpool_conf = self.pgpoolpath + '/etc/pgpool.conf'
        # 修改相应参数
        sf.exec_command(sed_replace("listen_addresses = 'localhost'", "listen_addresses = '*'", pgpool_conf))
        sf.exec_command(sed_replace("sr_check_user = 'nobody'", "sr_check_user = 'pgpool'", pgpool_conf))
        sf.exec_command(sed_replace("health_check_period = 0", "health_check_period = 5", pgpool_conf))
        sf.exec_command(sed_replace("health_check_timeout = 20", "health_check_timeout = 30", pgpool_conf))
        sf.exec_command(sed_replace("health_check_user = 'nobody'", "health_check_user = 'pgpool'", pgpool_conf))
        sf.exec_command(sed_replace("health_check_max_retries = 0", "health_check_max_retries = 3", pgpool_conf))
        # 此处可能需要修改
        sf.exec_command(
            sed_replace("backend_hostname0 = 'localhost'", "backend_hostname0 = '%s'" % server[0], pgpool_conf))
        # 端口号配置可能需修改
        sf.exec_command(sed_replace("backend_port0 = 5432", "backend_port0 = 5432", pgpool_conf))
        sf.exec_command(sed_replace("backend_weight0 = 1", "backend_weight0 = 1", pgpool_conf))
        # 此处数据库默认名称为data,后续改
        sf.exec_command(sed_replace("backend_data_directory0 = '/var/lib/pgsql/data'",
                                    "backend_data_directory0 = '%s/data'" % self.pgpath, pgpool_conf))
        sf.exec_command(
            sed_replace("backend_flag0 = 'ALLOW_TO_FAILOVER'", "backend_flag0 = 'ALLOW_TO_FAILOVER'", pgpool_conf))
        # 此处需要修改！！！！！！！！！！！！
        sf.exec_command(
            sed_replace("#backend_hostname1 = 'host2'", "backend_hostname1 = '%s'" % self.standby01_node, pgpool_conf))
        sf.exec_command(sed_replace("#backend_port1 = 5433", "backend_port1 = 5432", pgpool_conf))
        sf.exec_command(
            sed_replace("#backend_data_directory1 = '/data1'", "backend_data_directory1 = '%s/data'" % self.pgpath,
                        pgpool_conf))
        sf.exec_command(
            sed_replace("#backend_flag1 = 'ALLOW_TO_FAILOVER'", "backend_flag1 = 'ALLOW_TO_FAILOVER'", pgpool_conf))
        # 添加backend_flag2的一些参数
        sf.exec_command(sed_add("backend_flag1 = 'ALLOW_TO_FAILOVER'",
                                "backend_hostname2 = '%s'\\nbackend_port2 = 5432\\nbackend_weight2 = 1" % self.standby02_node,
                                pgpool_conf))
        sf.exec_command(sed_add("backend_weight2",
                                "backend_data_directory2 = '%s/data'\\nbackend_flag2 = 'ALLOW_TO_FAILOVER'" % self.pgpath,
                                pgpool_conf))

        sf.exec_command(sed_replace("failover_command = ''",
                                    "failover_command = '/opt/pgpool-406/etc/failover.sh %d %h %p %D %m %H %M %P %r %R'",
                                    pgpool_conf))
        sf.exec_command(sed_replace("follow_master_command = ''",
                                    "follow_master_command = '/opt/pgpool-406/etc/follow_master.sh %d %h %p %D %m %M %H %P %r %R'",
                                    pgpool_conf))
        sf.exec_command(sed_replace("recovery_user = 'nobody'", "recovery_user = 'postgres'", pgpool_conf))
        sf.exec_command(
            sed_replace("recovery_1st_stage_command = ''", "recovery_1st_stage_command = 'recovery_1st_stage'",
                        pgpool_conf))
        sf.exec_command(sed_replace("enable_pool_hba = off", "enable_pool_hba = on", pgpool_conf))
        sf.exec_command(sed_replace("use_watchdog = off", "use_watchdog = on", pgpool_conf))
        sf.exec_command(sed_replace("delegate_IP = ''", "delegate_IP = '%s'" % self.delegate_ip, pgpool_conf))
        sf.exec_command(sed_replace(r"if_up_cmd = 'ip addr add \$_IP_\$/24 dev eth0 label eth0:0'",
                                    r"if_up_cmd = 'ip addr add \$_IP_\$/24 dev ens33 label ens33:0'", pgpool_conf))
        sf.exec_command(sed_replace(r"if_down_cmd = 'ip addr del \$_IP_\$/24 dev eth0'",
                                    r"if_down_cmd = 'ip addr del \$_IP_\$/24 dev ens33'", pgpool_conf))
        sf.exec_command(
            sed_replace(r"arping_cmd = 'arping -U \$_IP_\$ -w 1'", r"arping_cmd = 'arping -U \$_IP_\$ -w 1 -I ens33'",
                        pgpool_conf))
        sf.exec_command(sed_replace("wd_hostname = ''", "wd_hostname = '%s'" % server[0], pgpool_conf))
        # 去除本机IP，剩下其余两个IP，便于配置other_pgpool和heartbeat_distination等参数
        Other_2ip = []  # 用来装除了本机IP以外的两个IP
        for other_two_ip in three_ip.values():
            if server[0].strip() != other_two_ip:
                Other_2ip.append(other_two_ip)
        sf.exec_command(sed_replace("#other_pgpool_hostname0 = 'host0'", "other_pgpool_hostname0 = '%s'" % Other_2ip[0],
                                    pgpool_conf))
        sf.exec_command(sed_replace("#other_pgpool_port0 = 5432", "other_pgpool_port0 = 9999", pgpool_conf))
        sf.exec_command(sed_replace("#other_wd_port0 = 9000", "other_wd_port0 = 9000", pgpool_conf))
        sf.exec_command(sed_replace("#other_pgpool_hostname1 = 'host1'", "other_pgpool_hostname1 = '%s'" % Other_2ip[1],
                                    pgpool_conf))
        sf.exec_command(sed_replace("#other_pgpool_port1 = 5432", "other_pgpool_port1 = 9999", pgpool_conf))
        sf.exec_command(sed_replace("#other_wd_port1 = 9000", "other_wd_port1 = 9000", pgpool_conf))
        sf.exec_command(
            sed_replace("heartbeat_destination0 = 'host0_ip1'", "heartbeat_destination0 = '%s'" % Other_2ip[0],
                        pgpool_conf))
        sf.exec_command(
            sed_replace("#heartbeat_destination1 = 'host0_ip2'", "heartbeat_destination1 = '%s'" % Other_2ip[1],
                        pgpool_conf))
        sf.exec_command(
            sed_replace("#heartbeat_destination_port1 = 9694", "heartbeat_destination_port1 = 9694", pgpool_conf))
        sf.exec_command(sed_replace("#heartbeat_device1 = ''", "heartbeat_device1 = ''", pgpool_conf))
        sf.exec_command(sed_replace("log_destination = 'stderr'", "log_destination = 'syslog'", pgpool_conf))
        sf.exec_command(sed_replace("syslog_facility = 'LOCAL0'", "syslog_facility = 'LOCAL1'", pgpool_conf))
        sf.exec_command(sed_replace("pid_file_name = '/var/run/pgpool/pgpool.pid'",
                                    "pid_file_name = '%s/pgpool.pid'" % self.pgpoolpath, pgpool_conf))
        sf.exec_command(sed_replace("memqcache_oiddir = '/var/log/pgpool/oiddir'",
                                    "memqcache_oiddir = '%s/pgpool/oiddir'" % self.pgpoolpath, pgpool_conf))


        # POOL_hba.conf文件只需向里追加两行参数，在此就不另外写方法了
        sf.exec_command('cp {0}/etc/pool_hba.conf.sample {0}/etc/pool_hba.conf'.format(self.pgpoolpath))
        sf.exec_command(
            'echo "host    all             pgpool             0.0.0.0/0            md5">>{0}/etc/pool_hba.conf'.format(
                self.pgpoolpath))
        sf.exec_command(
            'echo "host    all             {0}             0.0.0.0/0            md5">>{1}/etc/pool_hba.conf'.format(
                parameters['dbusername'], self.pgpoolpath))

        sf.close()  # 关闭ssh连接对象

    def change_postgresql_conf_parameters(self, *server):
        '''此方法用于修改postgresql.conf文件和pg_hba.conf文件'''
        sf = self.ssh_connectionServer(*server)
        postgresql_conf = self.pgpath + '/data/postgresql.conf'
        sf.exec_command(sed_replace("#listen_addresses = 'localhost'", "listen_addresses = '*'", postgresql_conf))
        sf.exec_command(sed_replace("#archive_mode = off", "archive_mode = on", postgresql_conf))
        # 创建归档日志需要的文件夹
        sf.exec_command('mkdir {}/archivedir'.format(self.pgpath))
        sf.exec_command(
            sed_replace("#archive_command = ''", "archive_command ='cp %p {}/archivedir/%f'".format(self.pgpath),
                        postgresql_conf))
        sf.exec_command(sed_replace("#max_wal_senders = 10", "max_wal_senders = 10", postgresql_conf))

        # pg_hba.conf需要修改一个参数，就不单独写方法，添加到此方法一起就行了
        # 要配置子网掩码，将VIP拆分,IP的主机号变为0
        ip_list = parameters['delegate_ip'].split('.')[0:3]
        ip_list.append('0')
        netaddress = '.'.join(ip_list) + '/24'
        sf.exec_command(
            'echo "host    all             all             {0}            trust" >> {1}/data/pg_hba.conf'.format(
                netaddress, self.pgpath))
        sf.exec_command(
            'echo "host    all             all             0.0.0.0/0            trust" >> {1}/data/pg_hba.conf'.format(
                netaddress, self.pgpath))

        sf.close()


def sed_replace(replaced, replace, path):
    return '''sed -i "s|{0}|{1}|" {2}'''.format(replaced, replace, path)


def sed_add(after_line, add, path):
    return '''sed -i "/{0}/a{1}" {2}'''.format(after_line, add, path)


def check_exec_command(result, expect, describe_pass='符合预期', describe_fail='符合预期'):
    '''此方法用于验证exec_command方法返回的结果是否符合预期
       result：接收exec_command的返回值
       expect:期望返回值中包含的字符串，多种期望可用 | 隔开
       describe_fail:对不符合预期场景进行描述
       describe_pass:对预期结果进行描述
    '''
    stdin, stdout, stderr = result
    res, err = stdout.read(), stderr.read()
    result = res + err
    if not re.search(expect, result.decode()):
        raise Exception(describe_fail, result.decode())
    else:
        print(describe_pass)


if __name__ == '__main__':
    pgpoolconfiguer = PgpoolConfigure(parameters['primary_node_ip'],
                                      parameters['standby01_node_ip'],
                                      parameters['standby02_node_ip'],
                                      parameters['pgpath'],
                                      parameters['pgpoolpath'],
                                      parameters['delegate_ip'])
    jobs4 = []
    jobs0 = []
    jobs1 = []
    jobs2 = []
    jobs3 = []
    for server_ip in [parameters['primary_node_ip'], parameters['standby01_node_ip'], parameters['standby02_node_ip']]:
        p4 = multiprocessing.Process(target=pgpoolconfiguer.check_data_status,
                                     args=(server_ip, parameters['dbusername'], parameters['dbpasswd']))
        p0 = multiprocessing.Process(target=pgpoolconfiguer.basic_setting_by_dbuser,
                                     args=(server_ip, parameters['dbusername'], parameters['dbpasswd']))
        p1 = multiprocessing.Process(target=pgpoolconfiguer.basic_setting,
                                     args=(server_ip, 'root', parameters['root_password']))
        p2 = multiprocessing.Process(target=pgpoolconfiguer.change_pgpool_conf_parameters,
                                     args=(server_ip, 'root', parameters['root_password']),
                                     # args按连接ip、连接用户名、连接密码排序
                                     kwargs={'a': parameters['primary_node_ip'], 'b': parameters['standby01_node_ip'],
                                             'c': parameters['standby02_node_ip']})
        p3 = multiprocessing.Process(target=pgpoolconfiguer.change_postgresql_conf_parameters,
                                     args=(server_ip, parameters['dbusername'], parameters['dbpasswd']))


        jobs4.append(p4)
        jobs0.append(p0)
        jobs1.append(p1)
        jobs2.append(p2)
        jobs3.append(p3)
        p4.start()
        p0.start()
        p1.start()
        p2.start()
        p3.start()

    for job in range(3):
        p4.join()
        p0.join()
        p1.join()
        p2.join()
        p3.join()
