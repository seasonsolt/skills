#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("resolve_codex_session_scope.py")
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("resolve_codex_session_scope", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolver)


class ResolveCodexSessionScopeTest(unittest.TestCase):
    def test_direct_work_directory_is_included(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work_root = Path(temp_dir) / "company"
            cwd = work_root / "project"
            cwd.mkdir(parents=True)
            result = resolver.resolve_scope(cwd.as_posix(), [work_root.resolve()], Path(temp_dir) / "codex")
            self.assertTrue(result["included"])
            self.assertEqual(result["mode"], "direct")

    def test_verified_codex_worktree_is_included(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            work_root = base / "company"
            source = work_root / "project"
            codex_root = base / ".codex" / "worktrees"
            worktree = codex_root / "123" / "project"
            source.mkdir(parents=True)
            worktree.parent.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "--allow-empty",
                    "-q",
                    "-m",
                    "initial",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(source), "worktree", "add", "-q", "-b", "test-worktree", str(worktree)],
                check=True,
            )

            result = resolver.resolve_scope(
                worktree.as_posix(), [work_root.resolve()], codex_root.resolve()
            )
            self.assertTrue(result["included"])
            self.assertEqual(result["mode"], "codex_worktree")
            self.assertEqual(Path(result["sourceRoot"]), source.resolve())

    def test_unverified_external_directory_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            work_root = base / "company"
            outside = base / "scratch"
            work_root.mkdir()
            outside.mkdir()
            result = resolver.resolve_scope(
                outside.as_posix(), [work_root.resolve()], base / ".codex" / "worktrees"
            )
            self.assertFalse(result["included"])
            self.assertEqual(result["mode"], "excluded")


if __name__ == "__main__":
    unittest.main()
