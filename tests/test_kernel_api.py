import os
import tempfile
import unittest

import requests

from kernel_api import (
    KernelApiScheduler,
    build_file_focus_slice,
    prepare_commit_cache,
    strip_redundant_lines,
)


class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}: {self.text}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "headers": headers or {},
                "params": params or {},
                "timeout": timeout,
            }
        )
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class KernelApiTests(unittest.TestCase):
    def test_strip_redundant_lines(self):
        message = "Fix bug\nSigned-off-by: person\nReviewed-by: reviewer\nKeep this line"
        self.assertEqual(strip_redundant_lines(message), "Fix bug\nKeep this line")

    def test_scheduler_backs_off_on_rate_limit(self):
        sleeps = []
        session = FakeSession(
            [
                FakeResponse(
                    403,
                    {"message": "rate limit"},
                    headers={
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": "101",
                    },
                ),
                FakeResponse(
                    200,
                    {"ok": True},
                    headers={
                        "X-RateLimit-Remaining": "9",
                        "X-RateLimit-Reset": "200",
                    },
                ),
            ]
        )
        scheduler = KernelApiScheduler(
            token="token",
            session=session,
            sleep_fn=sleeps.append,
            time_fn=lambda: 100,
            min_interval=0,
        )

        payload = scheduler.request_json("/test")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(len(session.calls), 2)
        self.assertTrue(any(wait >= 1 for wait in sleeps))

    def test_scheduler_retries_ssl_error(self):
        sleeps = []
        session = FakeSession(
            [
                requests.exceptions.SSLError("temporary eof"),
                FakeResponse(
                    200,
                    {"ok": True},
                    headers={
                        "X-RateLimit-Remaining": "9",
                        "X-RateLimit-Reset": "200",
                    },
                ),
            ]
        )
        scheduler = KernelApiScheduler(
            token="token",
            session=session,
            sleep_fn=sleeps.append,
            time_fn=lambda: 100,
            min_interval=0,
            max_ssl_retries=2,
            ssl_retry_backoff=0.5,
        )

        payload = scheduler.request_json("/test")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(len(session.calls), 2)
        self.assertIn(0.5, sleeps)

    def test_build_file_focus_slice_from_snapshot_respects_budget(self):
        file_content = "\n".join(
            [
                "static int member_address_is_nonnull(int *ptr)",
                "{",
                "    int value = *ptr;",
                "    if (value > 0)",
                "        return value;",
                "    return 0;",
                "}",
                "",
                "static int other(void)",
                "{",
                "    return 1;",
                "}",
            ]
        )
        patch = "\n".join(
            [
                "@@ -1,6 +1,6 @@ static int member_address_is_nonnull(int *ptr)",
                "-    int value = ptr[0];",
                "+    int value = *ptr;",
                "     if (value > 0)",
                "         return value;",
            ]
        )

        slices = build_file_focus_slice(
            "deadbeef",
            "kernel/file.c",
            patch,
            line_budget=5,
            file_content=file_content,
            context_lines=1,
            max_slices=1,
        )

        self.assertEqual(len(slices), 1)
        self.assertEqual(slices[0]["source_type"], "focus_slice")
        self.assertIn("member_address_is_nonnull", slices[0]["content"])
        self.assertLessEqual(len(slices[0]["content"].splitlines()), 5)

    def test_build_file_focus_slice_uses_pre_patch_old_start(self):
        file_content = "\n".join(
            [
                "line 1",
                "line 2",
                "line 3",
                "line 4",
                "line 5",
                "line 6",
                "line 7",
                "line 8",
            ]
        )
        patch = "\n".join(
            [
                "@@ -2,2 +5,3 @@ static void foo(void)",
                "-line 2",
                "-line 3",
                "+line 5",
                "+line 5.1",
                "+line 6",
            ]
        )

        slices = build_file_focus_slice(
            "deadbeef",
            "kernel/file.c",
            patch,
            line_budget=6,
            file_content=file_content,
            context_lines=0,
            max_slices=1,
        )

        content = slices[0]["content"]
        self.assertIn("    2 line 2", content)
        self.assertIn("    3 line 3", content)
        self.assertNotIn("    5 line 5", content)

    def test_build_file_focus_slice_falls_back_to_patch_hunks(self):
        patch = "\n".join(
            [
                "@@ -10,2 +10,3 @@ static void foo(void)",
                "-\treturn;",
                "+\tbar();",
                "+\treturn;",
            ]
        )
        slices = build_file_focus_slice(
            "deadbeef",
            "kernel/file.c",
            patch,
            line_budget=20,
            file_content=None,
            max_slices=1,
        )
        self.assertEqual(slices[0]["source_type"], "patch_hunk")
        self.assertIn("@@ -10,2 +10,3 @@", slices[0]["content"])

    def test_prepare_commit_cache_prefers_disk_cache_on_repeat(self):
        seed_report = {
            "id": "abc123",
            "year": "2024",
            "message": "foo: fix compiler-induced loop\n\nClang made the loop infinite.",
            "patches": {
                "drivers/foo.c": "\n".join(
                    [
                        "@@ -1,2 +1,2 @@ static int foo(void)",
                        "-\treturn 0;",
                        "+\treturn 1;",
                    ]
                )
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = prepare_commit_cache(
                "abc123",
                cache_dir=tmpdir,
                seed_data=seed_report,
                scheduler=None,
                policy={"fetch_snapshots": False},
            )
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "abc123.json")))

            class ExplodingScheduler:
                def fetch_commit_info(self, commit_sha):
                    raise AssertionError("should not fetch when cache file already exists")

                def fetch_file_snapshot(self, commit_sha, file_path):
                    raise AssertionError("should not fetch when cache file already exists")

            cached_again = prepare_commit_cache(
                "abc123",
                cache_dir=tmpdir,
                seed_data=seed_report,
                scheduler=ExplodingScheduler(),
                policy={"fetch_snapshots": False},
            )

            self.assertEqual(cache["message"], cached_again["message"])
            self.assertEqual(cache["files"][0]["file_path"], cached_again["files"][0]["file_path"])
            self.assertEqual(len(cache["digest_contexts"]), 1)
            self.assertEqual(
                cache["digest_contexts"][0]["file_path"],
                "drivers/foo.c",
            )
            self.assertIn(
                "Changed symbols:",
                cache["digest_contexts"][0]["summary"],
            )

    def test_prepare_commit_cache_fetches_parent_snapshot(self):
        seed_report = {
            "id": "abc123",
            "parent_id": "parent456",
            "year": "2024",
            "message": "foo: fix compiler-induced loop\n\nClang made the loop infinite.",
            "patches": {
                "drivers/foo.c": "\n".join(
                    [
                        "@@ -2,2 +2,2 @@ static int foo(void)",
                        "-\treturn 0;",
                        "+\treturn 1;",
                    ]
                )
            },
        }

        class RecordingScheduler:
            def __init__(self):
                self.calls = []
                self.rate_limit = {}

            def fetch_commit_info(self, commit_sha):
                raise AssertionError("seed data should satisfy commit bundle in this test")

            def fetch_file_snapshot(self, commit_sha, file_path):
                self.calls.append((commit_sha, file_path))
                return "static int foo(void)\n{\n\treturn 0;\n}\n"

        scheduler = RecordingScheduler()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = prepare_commit_cache(
                "abc123",
                cache_dir=tmpdir,
                seed_data=seed_report,
                scheduler=scheduler,
                policy={"fetch_snapshots": True},
            )

            self.assertEqual(scheduler.calls, [("parent456", "drivers/foo.c")])
            self.assertEqual(cache["parent_id"], "parent456")
            self.assertEqual(cache["files"][0]["snapshot_ref"], "parent456")


if __name__ == "__main__":
    unittest.main()
