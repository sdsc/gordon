Gordon Compute Node Hardware Check
==================================

Check status function:

  Checks an exit status, and append the error string if not zero.

Checks & Actions
----------------

1. Remove /.rocks-release (ensure repartitioning on reinstall)
2. Check IB cards exist and ports active
3. Call check memory script
4. Count CPUs
5. Check Lustre is mounted
6. LNET ping MDSes
7. Check rpcbind
 * If down, restart
 * Restart channeld
8. Check automount
 * If down, restart
9. Offline if any fail

 
