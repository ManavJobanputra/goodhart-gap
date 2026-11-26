# Blockers

(Each entry: `## B-NNN <title> (Mx) — status: OPEN|WORKAROUND|RESOLVED`.)

## B-001 Docker sandbox backend unimplemented (M2) — status: WORKAROUND
Symptom: `DockerSandbox.run_cases` raises NotImplementedError.
Tried: 1) Decided the subprocess backend is sufficient for the measurement
threat model (gaming, not kernel escape). 2) Left Docker as an optional stub.
Hypothesis: Not needed for the core research question.
Fallback in place: SubprocessSandbox (default) + macOS sandbox-exec network deny.
Human action: implement DockerSandbox only if stronger isolation is required.

