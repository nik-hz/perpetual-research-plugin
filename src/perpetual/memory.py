"""Git-backed markdown memory for the perpetual research agent."""

from __future__ import annotations

import os
import time
import warnings
from pathlib import Path
from typing import Dict, List, Optional

try:
    import pygit2

    _HAS_GIT = True
except ImportError:
    _HAS_GIT = False
    warnings.warn(
        "pygit2 not installed — memory will work without git history",
        stacklevel=2,
    )

_DEFAULT_FILES = {
    "index.md": "# Research Index\n\n_No entries yet._\n",
    "hypotheses.md": "# Hypotheses\n\n_No hypotheses yet._\n",
    "project.md": "# Project Context\n\n_Not configured._\n",
}

_SUBDIRS = ("details", "failures")


class Memory:
    """Persistent, git-backed markdown memory store.

    All paths passed to public methods are relative to *root*.
    """

    def __init__(self, root):
        # type: (str | Path) -> None
        self._root = Path(root).resolve()
        self._repo = None  # type: Optional[pygit2.Repository]
        self._ensure_layout()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _ensure_layout(self):
        # directories
        self._root.mkdir(parents=True, exist_ok=True)
        for sub in _SUBDIRS:
            (self._root / sub).mkdir(exist_ok=True)

        # default files (only create if missing)
        created = []
        for name, content in _DEFAULT_FILES.items():
            p = self._root / name
            if not p.exists():
                p.write_text(content, encoding="utf-8")
                created.append(name)

        # git repo
        if _HAS_GIT:
            self._init_repo(created or list(_DEFAULT_FILES))

    def _init_repo(self, seed_files):
        # type: (list[str]) -> None
        root_str = str(self._root)
        try:
            self._repo = pygit2.Repository(root_str)
        except pygit2.GitError:
            self._repo = pygit2.init_repository(root_str, bare=False)
            # stage seed files and make initial commit
            idx = self._repo.index
            idx.read()
            for name in _DEFAULT_FILES:
                fpath = self._root / name
                if fpath.exists():
                    idx.add(name)
            idx.write()
            tree_oid = idx.write_tree()
            sig = pygit2.Signature("perpetual", "perpetual@local")
            self._repo.create_commit(
                "refs/heads/master", sig, sig, "init memory", tree_oid, []
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _abs(self, path):
        # type: (str) -> Path
        return self._root / path

    def _relpath(self, abspath):
        # type: (Path) -> str
        return str(abspath.relative_to(self._root))

    def _sig(self):
        if _HAS_GIT:
            return pygit2.Signature("perpetual", "perpetual@local")
        return None

    def _git_commit(self, paths, message):
        # type: (list[str], str) -> None
        """Stage *paths* (relative to root) and commit."""
        if not _HAS_GIT or self._repo is None:
            return
        idx = self._repo.index
        idx.read()
        for p in paths:
            idx.add(p)
        idx.write()
        tree_oid = idx.write_tree()
        sig = self._sig()
        parents = []
        try:
            parents = [self._repo.head.target]
        except pygit2.GitError:
            pass
        self._repo.create_commit(
            "refs/heads/master", sig, sig, message, tree_oid, parents
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, path):
        # type: (str) -> str
        """Read a file relative to root. Raises FileNotFoundError."""
        return self._abs(path).read_text(encoding="utf-8")

    def write(self, path, content, message=None):
        # type: (str, str, Optional[str]) -> None
        """Write *content* atomically, then git-commit."""
        dest = self._abs(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(str(tmp), str(dest))
        self._git_commit([path], message or "update {}".format(path))

    def append(self, path, content, message=None):
        # type: (str, str, Optional[str]) -> None
        """Append *content* to file (create if missing), then git-commit."""
        dest = self._abs(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(str(dest), "a", encoding="utf-8") as f:
            f.write(content)
        self._git_commit([path], message or "update {}".format(path))

    def load_context(self):
        # type: () -> str
        """Return concatenation of the three core files with headers."""
        parts = []
        for name in ("index.md", "project.md", "hypotheses.md"):
            p = self._abs(name)
            if p.exists():
                parts.append(p.read_text(encoding="utf-8"))
            else:
                parts.append("# {}\n\n_(missing)_\n".format(name))
        return "\n---\n\n".join(parts)

    def log_failure(self, exp_id, summary):
        # type: (str, str) -> None
        """Write a failure report to failures/{exp_id}.md."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        content = "# Failure: {}\n\n**Time:** {}\n\n{}\n".format(exp_id, ts, summary)
        rel = "failures/{}.md".format(exp_id)
        self.write(rel, content, message="log failure {}".format(exp_id))

    def list_files(self, subdir=""):
        # type: (str) -> List[str]
        """List files in *subdir* (relative to root). Returns relative paths."""
        base = self._abs(subdir) if subdir else self._root
        if not base.is_dir():
            return []
        results = []
        for entry in sorted(base.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_file():
                results.append(self._relpath(entry))
        return results

    def history(self, path, n=10):
        # type: (str, int) -> List[Dict]
        """Return last *n* commits that touched *path*."""
        if not _HAS_GIT or self._repo is None:
            return []
        results = []
        try:
            head = self._repo.head.target
        except pygit2.GitError:
            return []
        for commit in self._repo.walk(head, pygit2.GIT_SORT_TIME):
            if len(results) >= n:
                break
            # check if path changed in this commit vs its first parent
            try:
                entry = commit.tree[path]
            except KeyError:
                continue
            if commit.parents:
                try:
                    parent_entry = commit.parents[0].tree[path]
                    if parent_entry.id == entry.id:
                        continue  # unchanged
                except KeyError:
                    pass  # file added in this commit
            # root commit or file changed
            results.append(
                {
                    "hash": str(commit.id),
                    "message": commit.message.strip(),
                    "timestamp": commit.commit_time,
                }
            )
        return results
