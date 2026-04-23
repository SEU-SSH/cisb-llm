import os
import tempfile
import unittest
from argparse import Namespace

from run_agentic_kernel import resolve_commit_targets, resolve_persistence_options


class RunAgenticKernelTests(unittest.TestCase):
    def test_resolve_commit_targets_from_file(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
            f.write("abc\n\nxyz\n")
            path = f.name

        try:
            targets = resolve_commit_targets(commits_file=path)
            self.assertEqual(targets, ["abc", "xyz"])
        finally:
            os.remove(path)

    def test_resolve_commit_targets_single_commit(self):
        targets = resolve_commit_targets(commit_id="deadbeef")
        self.assertEqual(targets, ["deadbeef"])

    def test_resolve_commit_targets_rejects_mixed_modes(self):
        with self.assertRaises(ValueError):
            resolve_commit_targets(commit_id="deadbeef", commits_file="commits.txt")

    def test_resolve_persistence_options_normal_defaults(self):
        args = Namespace(
            debug=False,
            persist_analysis=None,
            persist_trace=None,
            persist_digest=None,
        )
        self.assertEqual(
            resolve_persistence_options(args),
            {"analysis": True, "trace": False, "digest": False},
        )

    def test_resolve_persistence_options_debug_defaults(self):
        args = Namespace(
            debug=True,
            persist_analysis=None,
            persist_trace=None,
            persist_digest=None,
        )
        self.assertEqual(
            resolve_persistence_options(args),
            {"analysis": True, "trace": True, "digest": False},
        )

    def test_resolve_persistence_options_explicit_override(self):
        args = Namespace(
            debug=True,
            persist_analysis=False,
            persist_trace=False,
            persist_digest=True,
        )
        self.assertEqual(
            resolve_persistence_options(args),
            {"analysis": False, "trace": False, "digest": True},
        )


if __name__ == "__main__":
    unittest.main()
