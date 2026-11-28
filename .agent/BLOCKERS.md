# Blockers

(Each entry: `## B-NNN <title> (Mx) — status: OPEN|WORKAROUND|RESOLVED`.)

## B-001 Docker sandbox backend unimplemented (M2) — status: WORKAROUND
Symptom: `DockerSandbox.run_cases` raises NotImplementedError.
Tried: 1) Decided the subprocess backend is sufficient for the measurement
threat model (gaming, not kernel escape). 2) Left Docker as an optional stub.
Hypothesis: Not needed for the core research question.
Fallback in place: SubprocessSandbox (default) + macOS sandbox-exec network deny.
Human action: implement DockerSandbox only if stronger isolation is required.

## B-002 Orphaned sandbox children if the parent is SIGKILLed (M4/M10) — status: WORKAROUND
Symptom: A long build/calibrate killed with SIGKILL (e.g. `pkill`) can leave
`child_runner` processes re-parented to init, burning CPU indefinitely. Observed
during the benchmark rebuild (two orphans at 100% CPU for ~45 min).
Cause: the RSS watchdog / timeout kill runs on a thread in the *parent*; if the
parent dies abruptly the thread is gone, and the child (started with
`start_new_session=True` so grandchildren can't outlive the grader) survives in
its own session. macOS has no `PR_SET_PDEATHSIG`.
Workaround: before launching a long run, `pkill -f child_runner` any orphan
(PPID 1) children; a normal (non-SIGKILL) exit or timeout kills the group
correctly. Prefer letting runs finish or interrupt with SIGINT, not SIGKILL.
Human action: add a startup reaper that kills orphaned `child_runner` with PPID 1
older than N minutes, or wrap the parent in a supervisor, if this recurs.


