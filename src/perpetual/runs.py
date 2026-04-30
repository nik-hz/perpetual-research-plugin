"""Run tracking and watchdog module.

Manages experiment subprocess lifecycles: launch, monitor via background
watchdog threads, scan for status, and kill on request.
"""

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path


# Patterns in stdout/stderr that indicate a likely failure.
# These are checked as whole-word or phrase matches via _has_failure_pattern().
_FAILURE_PATTERNS = ("NaN", "OOM", "CUDA error", "RuntimeError", "out of memory")

_HEARTBEAT_INTERVAL = 30  # seconds
_STALE_THRESHOLD = 120    # seconds


class RunManager:
    """Track and supervise experiment runs under a shared runs directory."""

    def __init__(self, runs_dir):
        # type: (str | Path) -> None
        self._runs_dir = Path(runs_dir)
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        # Guards _active so launch/kill don't race on the same exp_id.
        self._lock = threading.Lock()
        # exp_id -> (Popen, Thread)
        self._active = {}

    # ------------------------------------------------------------------
    # Launch
    # ------------------------------------------------------------------

    # @sig e38d6175 | role: launch_run | by: claude-code-b7232740 | at: 2026-04-29T22:57:22Z
    def launch_run(self, exp_id, command, gpu_devices=None, env=None):
        # type: (str, str | list, list[int] | None, dict | None) -> dict
        """Launch *command* as a subprocess and begin watchdog monitoring.

        Returns ``{exp_id, pid, run_dir}``.
        """
        run_dir = self._runs_dir / exp_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # ---- config.json ----
        config = {
            "exp_id": exp_id,
            "command": command,
            "gpu_devices": gpu_devices,
            "env": env,
        }
        _write_json(run_dir / "config.json", config)

        # ---- environment ----
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)
        if gpu_devices is not None:
            proc_env["CUDA_VISIBLE_DEVICES"] = ",".join(str(d) for d in gpu_devices)

        # ---- subprocess ----
        stdout_path = run_dir / "stdout.log"
        stderr_path = run_dir / "stderr.log"

        shell = isinstance(command, str)
        fout = open(stdout_path, "w")
        ferr = open(stderr_path, "w")
        try:
            proc = subprocess.Popen(
                command,
                shell=shell,
                stdout=fout,
                stderr=ferr,
                env=proc_env,
                start_new_session=True,
            )
        except Exception:
            fout.close()
            ferr.close()
            raise

        # ---- metadata.json ----
        started_at = _now_iso()
        metadata = {
            "pid": proc.pid,
            "started_at": started_at,
            "status": "running",
        }
        _write_json(run_dir / "metadata.json", metadata)

        # ---- watchdog ----
        t = threading.Thread(
            target=self._watchdog,
            args=(exp_id, proc, run_dir, started_at, fout, ferr),
            daemon=True,
            name=f"watchdog-{exp_id}",
        )
        with self._lock:
            self._active[exp_id] = (proc, t)
        t.start()

        return {"exp_id": exp_id, "pid": proc.pid, "run_dir": str(run_dir)}

    # ------------------------------------------------------------------
    # Watchdog (runs in a daemon thread per experiment)
    # ------------------------------------------------------------------

    # @sig 80ae718c | role: _watchdog | by: claude-code-993d23b6 | at: 2026-04-30T04:51:35Z
    def _watchdog(self, exp_id, proc, run_dir, started_at, fout=None, ferr=None):
        # type: (str, subprocess.Popen, Path, str, ..., ...) -> None
        """Poll the process every *_HEARTBEAT_INTERVAL* seconds.

        Writes heartbeat, detects exit, and scans logs for failure patterns.
        """
        crash_written = False

        try:
            while True:
                alive = proc.poll() is None

                # ---- heartbeat ----
                _write_json(run_dir / "heartbeat.json", {
                    "timestamp": _now_iso(),
                    "pid": proc.pid,
                    "alive": alive,
                })

                if not alive:
                    # Process has exited.
                    rc = proc.returncode
                    finished_at = _now_iso()
                    duration = _duration_seconds(started_at, finished_at)

                    if rc == 0:
                        _write_json(run_dir / "done.json", {
                            "finished_at": finished_at,
                            "returncode": rc,
                            "duration_seconds": duration,
                        })
                    else:
                        last_stderr = _tail(run_dir / "stderr.log", 50)
                        _write_json(run_dir / "crash.json", {
                            "finished_at": finished_at,
                            "returncode": rc,
                            "duration_seconds": duration,
                            "last_stderr": last_stderr,
                        })

                    with self._lock:
                        self._active.pop(exp_id, None)
                    return

                # ---- scan logs for failure patterns while still running ----
                if not crash_written:
                    pattern = _scan_for_failures(run_dir / "stdout.log", run_dir / "stderr.log")
                    if pattern is not None:
                        _write_json(run_dir / "crash.json", {
                            "detected_at": _now_iso(),
                            "pattern": pattern,
                            "note": "Failure pattern detected but process still running.",
                        })
                        crash_written = True

                time.sleep(_HEARTBEAT_INTERVAL)
        finally:
            # Close file handles passed from launch_run
            for fh in (fout, ferr):
                if fh is not None:
                    try:
                        fh.close()
                    except Exception:
                        pass

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    # @sig e53fc4df | role: scan_runs | by: claude-code-993d23b6 | at: 2026-04-30T04:56:50Z
    def scan_runs(self):
        # type: () -> list[dict]
        """Return a status summary for every run directory."""
        results = []
        if not self._runs_dir.is_dir():
            return results

        for entry in sorted(self._runs_dir.iterdir()):
            if not entry.is_dir():
                continue

            exp_id = entry.name
            meta = _read_json(entry / "metadata.json") or {}
            started_at = meta.get("started_at")

            # Determine status from marker files.
            if (entry / "done.json").exists():
                status = "done"
                details = _read_json(entry / "done.json") or {}
            elif (entry / "crash.json").exists():
                status = "crashed"
                details = _read_json(entry / "crash.json") or {}
            else:
                # No marker file — check if process is actually alive.
                pid = meta.get("pid")
                proc_alive = _pid_alive(pid) if pid else False

                if not proc_alive and pid:
                    # Process exited but watchdog didn't write a marker.
                    # Check stderr for failure patterns and stderr content
                    # to decide crash vs done.
                    pattern = _scan_for_failures(
                        entry / "stdout.log", entry / "stderr.log"
                    )
                    stderr_content = _tail(entry / "stderr.log", 50)
                    finished_at = _now_iso()
                    duration = _duration_seconds(started_at, finished_at) if started_at else 0.0
                    if pattern or stderr_content.strip():
                        _write_json(entry / "crash.json", {
                            "finished_at": finished_at,
                            "duration_seconds": duration,
                            "pattern": pattern,
                            "last_stderr": stderr_content,
                            "note": "detected by scan (watchdog missed exit)",
                        })
                        status = "crashed"
                        details = _read_json(entry / "crash.json") or {}
                    else:
                        _write_json(entry / "done.json", {
                            "finished_at": finished_at,
                            "duration_seconds": duration,
                            "returncode": None,
                            "note": "detected by scan (watchdog missed exit)",
                        })
                        status = "done"
                        details = _read_json(entry / "done.json") or {}
                else:
                    # Check heartbeat staleness.
                    hb = _read_json(entry / "heartbeat.json")
                    if hb is None:
                        status = "stale"
                        details = {"reason": "no heartbeat file"}
                    else:
                        age = _seconds_since(hb.get("timestamp"))
                        if age is not None and age > _STALE_THRESHOLD:
                            status = "stale"
                            details = {"last_heartbeat": hb.get("timestamp"), "age_seconds": round(age, 1)}
                        else:
                            status = "running"
                            details = {"pid": hb.get("pid")}

            results.append({
                "exp_id": exp_id,
                "status": status,
                "started_at": started_at,
                "details": details,
            })

        return results

    # ------------------------------------------------------------------
    # Kill
    # ------------------------------------------------------------------

    def kill_run(self, exp_id):
        # type: (str) -> bool
        """Send SIGTERM to the process group of *exp_id*.

        Writes a ``crash.json`` noting the kill and returns ``True``.
        Returns ``False`` if the run was not found or already dead.
        """
        run_dir = self._runs_dir / exp_id
        meta = _read_json(run_dir / "metadata.json")
        if meta is None:
            return False

        pid = meta.get("pid")
        if pid is None:
            return False

        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            return False

        _write_json(run_dir / "crash.json", {
            "finished_at": _now_iso(),
            "returncode": None,
            "note": "killed by user",
        })
        return True

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    def get_run(self, exp_id):
        # type: (str) -> dict | None
        """Merge all JSON files from a run directory into a single dict."""
        run_dir = self._runs_dir / exp_id
        if not run_dir.is_dir():
            return None

        merged = {}
        for p in sorted(run_dir.glob("*.json")):
            data = _read_json(p)
            if data is not None:
                merged[p.stem] = data
        return merged if merged else None


# ======================================================================
# Helpers
# ======================================================================

def _write_json(path, obj):
    # type: (Path, object) -> None
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(str(tmp), str(path))


def _read_json(path):
    # type: (Path) -> dict | None
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _now_iso():
    # type: () -> str
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(iso_str):
    # type: (str) -> datetime
    """Parse an ISO 8601 datetime string, compatible with Python 3.8+."""
    from datetime import datetime, timezone
    # Python 3.8-3.10 fromisoformat can't handle timezone offset; strip and re-add
    s = iso_str
    if s.endswith("+00:00") or s.endswith("Z"):
        s = s.replace("+00:00", "").replace("Z", "")
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    # Try standard parsing for other formats
    return datetime.fromisoformat(s)


# @sig f5411ab6 | role: _duration_seconds | by: claude-code-b7232740 | at: 2026-04-29T22:57:03Z
def _duration_seconds(started_iso, finished_iso):
    # type: (str, str) -> float
    try:
        t0 = _parse_iso(started_iso)
        t1 = _parse_iso(finished_iso)
        return round((t1 - t0).total_seconds(), 2)
    except (ValueError, TypeError):
        return 0.0


# @sig 5c5cd8dc | role: _seconds_since | by: claude-code-b7232740 | at: 2026-04-29T22:57:03Z
def _seconds_since(iso_str):
    # type: (str) -> float | None
    if iso_str is None:
        return None
    from datetime import datetime, timezone
    try:
        then = _parse_iso(iso_str)
        now = datetime.now(timezone.utc)
        return (now - then).total_seconds()
    except (ValueError, TypeError):
        return None


def _tail(path, n):
    # type: (Path, int) -> str
    """Return the last *n* lines of a file as a single string."""
    try:
        with open(path) as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except (FileNotFoundError, OSError):
        return ""


def _pid_alive(pid):
    # type: (int) -> bool
    """Check if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


# @sig c8eac4f7 | role: _scan_for_failures | by: claude-code-b7232740 | at: 2026-04-29T22:57:16Z
def _scan_for_failures(stdout_path, stderr_path):
    # type: (Path, Path) -> str | None
    """Return the first failure pattern found in either log, or None."""
    import re
    for path in (stdout_path, stderr_path):
        try:
            with open(path) as f:
                for line in f:
                    for pat in _FAILURE_PATTERNS:
                        # Use word-boundary match to avoid false positives
                        if re.search(r'\b' + re.escape(pat) + r'\b', line):
                            return pat
        except (FileNotFoundError, OSError):
            continue
    return None
