# !usr/bin/env python
# coding=utf-8
#此参数为安装编译pg和pgpool的参数，若只有1个IP，则其余键值对的值可填'',若不安装pgpool,则pgpoolpath和local_package_path1值为''
# example：
# setup= {
#     'pgusername': 'postgres',
#     'postgrespasswd':'123456',
#     'root_password': 'hg192168',
#     'remote_ip_0':'192.168.222.141',
#     'remote_ip_1':'192.168.222.142',
#     'remote_ip_2':'',
#     'pgpath': '/opt/PG-10.10',
#     'local_package_path0':'E:\materials\study_materials\package\postgresql-10.10.tar.gz',
#     'pgpoolpath':'/opt/pgpool-406',
#     'local_package_path1':'E:\materials\study_materials\package\pgpool-II-4.0.6.tar.gz'
#
# }

setup= {
    'pgusername': 'postgres',
    'postgrespasswd':'123456',
    'root_password': 'z1990712',
    #若安装少于3个IP，则多余的值填''
    'remote_ip_0':'192.168.222.141',
    'remote_ip_1':'',
    'remote_ip_2':'',
    'pgpath': '/opt/PG-10.10',
    'local_package_path0':'E:\materials\study_materials\package\postgresql-10.10.tar.gz',
    #若不选安装pgpool,则pgpoolpath，local_package_path1值为''.
    'pgpoolpath':'',
    'local_package_path1':''

}
