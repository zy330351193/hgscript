#!/bin/bash
# This script is run by failover_command.

set -o xtrace
exec > >(logger -i -p local1.info) 2>&1

# Special values:
#   %d = node id
#   %h = host name
#   %p = port number
#   %D = database cluster path
#   %m = new master node id
#   %H = hostname of the new master node
#   %M = old master node id
#   %P = old primary node id
#   %r = new master port number
#   %R = new master database cluster path
#   %% = '%' character

FAILED_NODE_ID="$1"
FAILED_NODE_HOST="$2"
FAILED_NODE_PORT="$3"
FAILED_NODE_PGDATA="$4"
NEW_MASTER_NODE_ID="$5"
NEW_MASTER_NODE_HOST="$6"
OLD_MASTER_NODE_ID="$7"
OLD_PRIMARY_NODE_ID="$8"
NEW_MASTER_NODE_PORT="$9"
NEW_MASTER_NODE_PGDATA="${10}"

PGHOME=/opt/PG-10.10

logger -i -p local1.info failover.sh: start: failed_node_id=${FAILED_NODE_ID} old_primary_node_id=${OLD_PRIMARY_NODE_ID} \
    failed_host=${FAILED_NODE_HOST} new_master_host=${NEW_MASTER_NODE_HOST}

## Test passwrodless SSH
ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null postgres@${NEW_MASTER_NODE_HOST} -i ~/.ssh/id_rsa ls /tmp > /dev/null

if [ $? -ne 0 ]; then
    logger -i -p local1.error failover.sh: passwrodless SSH to postgres@${NEW_MASTER_NODE_HOST} failed. Please setup passwrodless SSH.
    exit 1
fi

# If standby node is down, skip failover.
if [ ${FAILED_NODE_ID} -ne ${OLD_PRIMARY_NODE_ID} ]; then
    logger -i -p local1.info failover.sh: Standby node is down. Skipping failover.
    exit 0
fi

# Promote standby node.
logger -i -p local1.info failover.sh: Primary node is down, promote standby node PostgreSQL@${NEW_MASTER_NODE_HOST}.

ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
postgres@${NEW_MASTER_NODE_HOST} -i ~/.ssh/id_rsa ${PGHOME}/bin/pg_ctl -D ${NEW_MASTER_NODE_PGDATA} -w promote


if [ $? -ne 0 ]; then
    logger -i -p local1.error failover.sh: new_master_host=${NEW_MASTER_NODE_HOST} promote failed
    exit 1
fi

logger -i -p local1.info failover.sh: end: new_master_node_id=$NEW_MASTER_NODE_ID started as the primary node
exit 0