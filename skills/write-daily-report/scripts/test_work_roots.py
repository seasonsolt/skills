#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from work_roots import ENV_NAME, resolve_work_roots


class ResolveWorkRootsTest(unittest.TestCase):
    def test_explicit_roots_override_environment_and_deduplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            explicit = base / "explicit"
            configured = base / "configured"
            roots = resolve_work_roots(
                [str(explicit), str(explicit)],
                {ENV_NAME: str(configured)},
            )
            self.assertEqual(roots, [explicit.resolve()])

    def test_reads_multiple_roots_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            first = base / "company"
            second = base / "client"
            roots = resolve_work_roots(
                None,
                {ENV_NAME: os.pathsep.join((str(first), str(second)))},
            )
            self.assertEqual(roots, [first.resolve(), second.resolve()])

    def test_requires_an_explicit_or_configured_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "no work roots configured"):
            resolve_work_roots(None, {})


if __name__ == "__main__":
    unittest.main()
