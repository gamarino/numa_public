Description
===========

This module records exceptions on JsonRequests to the server
in a database table.
Instead of impacting the end user with a lot of information,
just an ID is shown to identify the particular exception
On recording, full information is recorded in order to 
ease the finding of root cause, including stack frames, 
a group of lines surranding the offending line and the
local values at the moment of the exception
It is more information than the standard frame.
Unless you mark the recorded exceptions with "Do not purge"
recorded exceptions are purged every day by a cron job
to guarantee that not usefull information remains more
than a month in database.
The fact you get variable values helps in situations where
non frequent cases aroses, preventing the typical reproduction
step for the programmer


