# Backup creation paused

Status: active

New backup, recovery-bundle, and recovery-drill artifacts are paused until
additional disk capacity is attached to the T480. The pause protects the
private runtime from further storage growth; it does not delete or invalidate
existing backups, and read-only manifest verification remains allowed.

The guarded paths are PostgreSQL logical backup, Wave 1 full-lab capture, M3
and Wave 1 synthetic recovery drills, and Penpot backup. Adapter operations
that invoke these paths fail through the same guard.

Resume only after an owner confirms the new storage is attached, verifies
adequate free capacity on the T480 through the governed status path, and
explicitly approves a tracked change that removes this pause. Do not bypass the
pause with a direct Docker command, environment variable, or an untracked copy
of a script.
