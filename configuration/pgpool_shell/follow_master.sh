#!/bin/bash
# This script is run after failover_command to synchronize the Standby with the new Primary.

set -o xtrace
exec > >(logger -i -p local1.info) 2>&1

# special values:  %d = node id
#                  %h = host name
#                  %p = port number
#                  %D = database cluster path
#                  %m = new master node id
#                  %M = old master node id
#                  %H = new master node host name
#                  %P = old primary node id
#                  %R = new master database cluster path
#                  %r = new master port number
#                  %% = '%' character
FAILED_NODE_ID="$1"
FAILED_NODE_HOST="$2"
FAILED_NODE_PORT="$3"
FAILED_NODE_PGDATA="$4"
NEW_MASTER_NODE_ID="$5"
OLD_MASTER_NODE_ID="$6"
NEW_MASTER_NODE_HOST="$7"
OLD_PRIMARY_NODE_ID="$8"
NEW_MASTER_NODE_PORT="$9"
NEW_MASTER_NODE_PGDATA="${10}"

PGHOME=/opt/PG-10.10
ARCHIVEDIR=/opt/PG-10.10/archivedir
REPL_USER=repl
PCP_USER=pgpool
PGPOOL_PATH=/opt/pgpool-406/bin
PCP_PORT=9898


# Recovery the slave from the new primary
logger -i -p local1.info follow_master.sh: start: synchronize the Standby node PostgreSQL@${FAILED_NODE_HOST} with the new Primary node PostgreSQL@${NEW_MASTER_NODE_HOST}

## Test passwrodless SSH
ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null postgres@${NEW_MASTER_NODE_HOST} -i ~/.ssh/id_rsa ls /tmp > /dev/null

if [ $? -ne 0 ]; then
    logger -i -p local1.error follow_master.sh: passwrodless SSH to postgres@${NEW_MASTER_NODE_HOST} failed. Please setup passwrodless SSH.
    exit 1
fi

## Get PostgreSQL major version
PGVERSION=`${PGHOME}/bin/initdb -V | awk '{print $3}' | sed 's/\..*//' | sed 's/\([0-9]*\)[a-zA-Z].*/\1/'`

if [ ${PGVERSION} -ge 12 ]; then
    RECOVERYCONF=${FAILED_NODE_PGDATA}/myrecovery.conf
else
    RECOVERYCONF=${FAILED_NODE_PGDATA}/recovery.conf
fi

# Check the status of standby
ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    postgres@${FAILED_NODE_HOST} -i ~/.ssh/id_rsa ${PGHOME}/bin/pg_ctl -w -D ${FAILED_NODE_PGDATA} status

## If Standby is running, run pg_basebackup.
if [ $? -eq 0 ]; then

    # Execute pg_basebackup
    ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null postgres@${FAILED_NODE_HOST} -i ~/.ssh/id_rsa "

        set -o errexit
        ${PGHOME}/bin/pg_ctl -w -m f -D ${FAILED_NODE_PGDATA} stop

        rm -rf ${FAILED_NODE_PGDATA}
        rm -rf ${ARCHIVEDIR}/*

        ${PGHOME}/bin/pg_basebackup -h ${NEW_MASTER_NODE_HOST} -U ${REPL_USER} -p ${NEW_MASTER_NODE_PORT} -D ${FAILED_NODE_PGDATA} -X stream

        if [ ${PGVERSION} -ge 12 ]; then
            sed -i -e \"\\\$ainclude_if_exists = '$(echo ${RECOVERYCONF} | sed -e 's/\//\\\//g')'\" \
                   -e \"/^include_if_exists = '$(echo ${RECOVERYCONF} | sed -e 's/\//\\\//g')'/d\" ${FAILED_NODE_PGDATA}/postgresql.conf
        fi

        cat > ${RECOVERYCONF} << EOT
primary_conninfo = 'host=${NEW_MASTER_NODE_HOST} port=${NEW_MASTER_NODE_PORT} user=${REPL_USER} passfile=''/home/postgres/.pgpass'''
recovery_target_timeline = 'latest'
restore_command = 'scp ${NEW_MASTER_NODE_HOST}:${ARCHIVEDIR}/%f %p'
EOT

        if [ ${PGVERSION} -ge 12 ]; then
            touch ${FAILED_NODE_PGDATA}/standby.signal
        else
            echo \"standby_mode = 'on'\" >> ${RECOVERYCONF}
        fi
    "

    if [ $? -ne 0 ]; then
        logger -i -p local1.error follow_master.sh: end: pg_basebackup failed
        exit 1
    fi

    # start Standby node on ${FAILED_NODE_HOST}
    ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
            postgres@${FAILED_NODE_HOST} -i ~/.ssh/id_rsa $PGHOME/bin/pg_ctl -l /dev/null -w -D ${FAILED_NODE_PGDATA} start

    # If start Standby successfully, attach this node
    if [ $? -eq 0 ]; then

        # Run pcp_attact_node to attach Standby node to Pgpool-II.
        ${PGPOOL_PATH}/pcp_attach_node -w -h localhost -U $PCP_USER -p ${PCP_PORT} -n ${FAILED_NODE_ID}

        if [ $? -ne 0 ]; then
            logger -i -p local1.error follow_master.sh: end: pcp_attach_node failed
            exit 1
        fi

    # If start Standby failed, drop replication slot "${FAILED_NODE_HOST}"
    else
        logger -i -p local1.error follow_master.sh: end: follow master command failed
        exit 1
    fi

else
    logger -i -p local1.info follow_master.sh: failed_nod_id=${FAILED_NODE_ID} is not running. skipping follow master command
    exit 0
fi

logger -i -p local1.info follow_master.sh: end: follow master command complete
exit 0