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


[1]: http://docs.adaptivecomputing.com/torque/Content/topics/12-appendices/prologueAndEpliogueScripts.htm
