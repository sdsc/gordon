Gordon Prologue & Epilogue
==========================

See the [Torque docs][1] for reference.

Note that the health check script is called at the beginning and end of
the job by Torque.

Prologue Actions
----------------

On Both, unless specified:

1. Check PBS ERROR
2. Remove leftover lock files
3. Create local scratch dir (check return status)
4. sdsc_stats
5. If dedicated, remove all job lock files
6. Create user-job lock file
7. 
 * On Mother Superior: Mkdir Oasis scratch (check return status)
 * On Sisters: Touch .OU and .ER files
8. Add user to access.conf

Epilogue Actions
----------------

On Both, unless specified:

1. Remove user from access.conf
2. Remove user-job lock file
3. Kill pstree of job script
4. If last job by user:
 * killall PIDs
 * clean files
 * semaphores
 * shm
5. sdsc_stats
6. Remove local scratch dir
7. Clean up /tmp
8. On Mother Superior: Remove Oasis scratch dir (check return status)

[1]: http://docs.adaptivecomputing.com/torque/Content/topics/12-appendices/prologueAndEpliogueScripts.htm
