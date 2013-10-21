#!/bin/bash
#
# This script is called by Torque at job start, job end,
# and at some interval of the polling interval.
#
# If any check fails the node is offlined with a note.
#
# The name is slightly misleading, since not all of the 
# checks are strictly hardware.

unhealthy=0
note=""

function check_status(){
    # $1 = expected value
    # $2 = status
    # $3 = message if different

    if [[ "$1" != "$2" ]] ; then
        unhealthy=1
	if [[ -z $note ]] ; then
            note=$3
	else
            note="$note; $3"
	fi
    fi
}

# Check 1 - IB cards

for card in mlx4_0 mlx4_1 ; do
    /usr/bin/ibv_devices | /bin/grep $card >& /dev/null
    check_status 0 $? "$card missing"
done

# Check 1.5 - IB ports
for card in mlx4_0 mlx4_1 ; do
    /usr/bin/ibv_devinfo -d $card | /bin/grep PORT_ACTIVE >& /dev/null
    check_status 0 $? "$card port not active"
done

# Check 2 - Memory

/opt/sdsc/sbin/check_mem >& /dev/null
check_status 0 $? "memory problems"

# Check 3 - Check CPUs

cpu_count=$(/bin/grep processor /proc/cpuinfo | /usr/bin/wc -l)
check_status 16 $cpu_count "processor count off"

# Check 4 - Check Lustre

# Check 4.1 monkey
/bin/grep monkey /etc/mtab > /dev/null 2>&1
if [[ "$?" -ne 0 ]] ; then
    /bin/mount /oasis/scratch 
    check_status 0 $? "oasis scratch problems"
else
    # LNET ping both MDSes and ensure that at least one responds
    /usr/sbin/lctl --net tcp ping 172.25.32.125  > /dev/null 2>&1
    mds1ping=$?
    /usr/sbin/lctl --net tcp ping 172.25.32.253  > /dev/null 2>&1
    mds2ping=$?
    check_status 0 $(( $mds1ping != 0 && $mds2ping != 0 )) "oasis scratch problems"
fi

# Check 4.2 meerkat
/bin/grep meerkat /etc/mtab >/dev/null 2>&1
if [[ "$?" -ne 0 ]] ; then
    /bin/mount /oasis/projects/nsf
    check_status 0 $? " oasis projects nsf problems"
else
    # LNET ping both MDSes and ensure that at least one responds
    /usr/sbin/lctl --net tcp ping 172.25.33.53  > /dev/null 2>&1
    mds1ping=$?
    /usr/sbin/lctl --net tcp ping 172.25.33.25  > /dev/null 2>&1
    mds2ping=$?
    check_status 0 $(( $mds1ping != 0 && $mds2ping != 0 )) "oasis projects nsf problems"
fi

# Check 5 - Check rpcbind

/etc/init.d/rpcbind status > /dev/null 2>&1
if [[ "$?" -ne 0 ]] ; then
    /etc/init.d/rpcbind  restart > /dev/null 2>&1
    rpcbind_status=$?
    check_status 0 $rpcbind_status " rpcbind not started"
    # if rpbcbind is bounced and is OK, need to restart channeld
    if [[ "$rpcbind_status" -eq 0 ]] ; then
        /etc/init.d/channeld restart
    fi
fi

# Check 6 - Check automount

/etc/init.d/autofs status > /dev/null 2>&1
if [[ "$?" -ne 0 ]] ; then
    /etc/init.d/autofs restart > /dev/null 2>&1
    check_status 0 $? "automount not running"
fi

# Check 7 - Check local disk usage

percent_disk_used=$( /bin/df / | /bin/grep sda | /bin/awk '{print $5}' | /usr/bin/tr -d '%' )
check_status 0 $(( $percent_disk_used > 90 )) "local disk full"

# Check 8 - test scratch file system
# TODO: Needs logic for "no flash" nodes
/bin/grep '^/dev/sdb /scratch xfs rw' /etc/mtab >/dev/null 2>&1
check_status 0 $? "iSER drive not mounted"
test_file_name=$(/usr/bin/uuidgen)
/bin/touch /scratch/.$test_file_name
check_status 0 $? "/scratch file system problems"
/bin/rm -f /scratch/.$test_file_name

# Report if any checks fail

if [[ "$unhealthy" -ne 0 ]] ; then
    echo "ERROR $note"
    exit -1
fi

exit 0
