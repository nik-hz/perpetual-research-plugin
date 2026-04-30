import json
import sqlite3
import threading
from pathlib import Path


class Graph:
    # @sig 263a4b40 | role: __init__ | by: claude-code-993d23b6 | at: 2026-04-30T03:13:52Z
    def __init__(self, db_path):
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        self._conn.close()

    def _init_schema(self):
        self._exec("""
            CREATE TABLE IF NOT EXISTS hypotheses (
                id TEXT PRIMARY KEY,
                claim TEXT NOT NULL,
                prior REAL NOT NULL DEFAULT 0.5,
                confidence REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'open',
                evidence TEXT DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
            )
        """)
        self._exec("""
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                hypothesis_id TEXT,
                status TEXT NOT NULL DEFAULT 'proposed',
                config TEXT NOT NULL DEFAULT '{}',
                results TEXT DEFAULT '{}',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
                FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(id)
            )
        """)
        self._exec("""
            CREATE TABLE IF NOT EXISTS budget_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                gpu_hours REAL NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            )
        """)

    def _exec(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _query(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    # @sig e67b27cc | role: _query_unlocked | by: claude-code-993d23b6 | at: 2026-04-30T04:29:20Z
    def _query_unlocked(self, sql, params=()):
        """Query without acquiring the lock (caller must hold it)."""
        cur = self._conn.execute(sql, params)
        return cur.fetchall()

    # @sig bc13c5d6 | role: _next_experiment_id | by: claude-code-993d23b6 | at: 2026-04-30T04:29:20Z
    def _next_experiment_id(self):
        """Must be called while holding self._lock."""
        rows = self._query_unlocked(
            "SELECT id FROM experiments WHERE id LIKE 'exp-%'"
        )
        if not rows:
            return "exp-001"
        num = max(int(r["id"].split("-")[1]) for r in rows) + 1
        return "exp-{:03d}".format(num)

    # @sig 02cb68fd | role: _next_hypothesis_id | by: claude-code-993d23b6 | at: 2026-04-30T04:29:20Z
    def _next_hypothesis_id(self):
        """Must be called while holding self._lock."""
        rows = self._query_unlocked(
            "SELECT id FROM hypotheses WHERE id LIKE 'hyp-%'"
        )
        if not rows:
            return "hyp-001"
        num = max(int(r["id"].split("-")[1]) for r in rows) + 1
        return "hyp-{:03d}".format(num)

    @staticmethod
    def _row_to_dict(row):
        if row is None:
            return None
        return dict(row)

    # -- Experiment CRUD --

    # @sig 85f4296a | role: add_experiment | by: claude-code-993d23b6 | at: 2026-04-30T04:29:04Z
    def add_experiment(self, id=None, hypothesis_id=None, config=None, notes=""):
        config_json = json.dumps(config) if config is not None else "{}"
        with self._lock:
            if id is None:
                id = self._next_experiment_id()
            self._conn.execute(
                "INSERT INTO experiments (id, hypothesis_id, config, notes) VALUES (?, ?, ?, ?)",
                (id, hypothesis_id, config_json, notes),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM experiments WHERE id = ?", (id,)).fetchone()
        return self._row_to_dict(row)

    def get_experiment(self, id):
        rows = self._query("SELECT * FROM experiments WHERE id = ?", (id,))
        if not rows:
            return None
        return self._row_to_dict(rows[0])

    def list_experiments(self, status=None):
        if status is not None:
            rows = self._query("SELECT * FROM experiments WHERE status = ?", (status,))
        else:
            rows = self._query("SELECT * FROM experiments")
        return [self._row_to_dict(r) for r in rows]

    def update_experiment(self, id, **kwargs):
        if not kwargs:
            return
        allowed = {"hypothesis_id", "status", "config", "results", "notes"}
        sets = []
        params = []
        for k, v in kwargs.items():
            if k not in allowed:
                raise ValueError("invalid column: {}".format(k))
            if k in ("config", "results"):
                v = json.dumps(v) if not isinstance(v, str) else v
            sets.append("{} = ?".format(k))
            params.append(v)
        sets.append("updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')")
        params.append(id)
        self._exec(
            "UPDATE experiments SET {} WHERE id = ?".format(", ".join(sets)),
            tuple(params),
        )

    # -- Hypothesis CRUD --

    # @sig 4813bad7 | role: add_hypothesis | by: claude-code-993d23b6 | at: 2026-04-30T04:29:36Z
    def add_hypothesis(self, id=None, claim="", prior=0.5):
        if not (0.0 <= prior <= 1.0):
            raise ValueError("prior must be between 0.0 and 1.0, got {}".format(prior))
        with self._lock:
            if id is None:
                id = self._next_hypothesis_id()
            self._conn.execute(
                "INSERT INTO hypotheses (id, claim, prior) VALUES (?, ?, ?)",
                (id, claim, prior),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM hypotheses WHERE id = ?", (id,)).fetchone()
        return self._row_to_dict(row)

    def get_hypothesis(self, id):
        rows = self._query("SELECT * FROM hypotheses WHERE id = ?", (id,))
        if not rows:
            return None
        return self._row_to_dict(rows[0])

    def list_hypotheses(self, status=None):
        if status is not None:
            rows = self._query("SELECT * FROM hypotheses WHERE status = ?", (status,))
        else:
            rows = self._query("SELECT * FROM hypotheses")
        return [self._row_to_dict(r) for r in rows]

    # @sig a783afab | role: update_hypothesis | by: claude-code-993d23b6 | at: 2026-04-30T03:13:47Z
    def update_hypothesis(self, id, **kwargs):
        if not kwargs:
            return
        if self.get_hypothesis(id) is None:
            raise KeyError("hypothesis not found: {}".format(id))
        allowed = {"claim", "prior", "confidence", "status", "evidence"}
        sets = []
        params = []
        for k, v in kwargs.items():
            if k not in allowed:
                raise ValueError("invalid column: {}".format(k))
            if k in ("prior", "confidence") and not (0.0 <= v <= 1.0):
                raise ValueError("{} must be between 0.0 and 1.0, got {}".format(k, v))
            if k == "evidence":
                v = json.dumps(v) if not isinstance(v, str) else v
            sets.append("{} = ?".format(k))
            params.append(v)
        sets.append("updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')")
        params.append(id)
        self._exec(
            "UPDATE hypotheses SET {} WHERE id = ?".format(", ".join(sets)),
            tuple(params),
        )

    # -- Budget --

    def log_budget(self, experiment_id, gpu_hours):
        cur = self._exec(
            "INSERT INTO budget_log (experiment_id, gpu_hours) VALUES (?, ?)",
            (experiment_id, gpu_hours),
        )
        row = self._query("SELECT * FROM budget_log WHERE id = ?", (cur.lastrowid,))
        return self._row_to_dict(row[0])

    def total_budget(self):
        rows = self._query("SELECT COALESCE(SUM(gpu_hours), 0.0) AS total FROM budget_log")
        return float(rows[0]["total"])

    def budget_by_experiment(self, experiment_id):
        rows = self._query(
            "SELECT COALESCE(SUM(gpu_hours), 0.0) AS total FROM budget_log WHERE experiment_id = ?",
            (experiment_id,),
        )
        return float(rows[0]["total"])
