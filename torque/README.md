Gordon Prologue & Epilogue
==========================

See the [Torque docs][1] for reference.

| File              | Runs on         | Calls           |
| ------------------|-----------------|-----------------|
| prologue          | Mother Superior | prologue.common |
| prologue.parallel | Sister          | prologue.common |
| prologue.common   | All nodes       |                 |
| epilogue          | Mother Superior | epilogue.common |
| epilogue.parallel | Sister          | epilogue.common |
| epilogue.common   | All nodes       |                 |

Prologue Actions
----------------

On Both:

1. Check PBS ERROR
2. Call hardware check
3. Remove leftover lock files
4. Create user-job lock file
5. Create local scratch dir (check return status)
6. Add user to access.conf
7. sdsc_stats

On Mother Superior:

1. Mkdir Oasis scratch (check return status)

On Sisters:

1. Touch .OU and .ER files

Epilogue Actions
----------------

On Both:

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

On Mother Superior:

1. Remove Oasis scratch dir (check return status)

[1]: http://docs.adaptivecomputing.com/torque/Content/topics/12-appendices/prologueAndEpliogueScripts.htm
