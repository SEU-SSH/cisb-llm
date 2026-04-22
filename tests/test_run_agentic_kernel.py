import os
import tempfile
import unittest

from run_agentic_kernel import resolve_commit_targets


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


if __name__ == "__main__":
    unittest.main()
