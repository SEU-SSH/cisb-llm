import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "agents"))

from agentic_kernel import (  # noqa: E402
    DigestorAgent,
    AgenticKernelOrchestrator,
    KernelRunState,
    KernelToolRegistry,
    QUESTION_TEXT,
    validate_reasoner_action,
)


def make_cache():
    return {
        "id": "abc123def456",
        "message": "llist: fix compiler-induced infinite loop\n\nClang assumes member address is non-null.",
        "overview": {
            "source_type": "commit_overview",
            "file_path": None,
            "commit_sha": "abc123def456",
            "line_hint": "message",
            "slice_id": "abc123def456:overview",
            "content": "Commit overview content",
        },
        "prioritized_files": ["include/linux/llist.h"],
        "files": [
            {
                "file_path": "include/linux/llist.h",
                "changes": 12,
                "priority_rank": 1,
                "patch": "@@ -1,2 +1,2 @@\n- old\n+ new\n",
                "focus_slices": [
                    {
                        "source_type": "focus_slice",
                        "file_path": "include/linux/llist.h",
                        "commit_sha": "abc123def456",
                        "line_hint": "L90-L110",
                        "slice_id": "abc123def456:include__linux__llist.h:focus:0",
                        "content": "  95 if (&pos->member != NULL)\n  96     return pos;",
                        "header": "llist_for_each_entry",
                    },
                    {
                        "source_type": "focus_slice",
                        "file_path": "include/linux/llist.h",
                        "commit_sha": "abc123def456",
                        "line_hint": "L145-L151",
                        "slice_id": "abc123def456:include__linux__llist.h:focus:1",
                        "content": " 145 if (member_address_is_nonnull(pos, member))\n 146     return pos;",
                        "header": "member_address_is_nonnull",
                    }
                ],
                "outline": {
                    "source_type": "file_outline",
                    "file_path": "include/linux/llist.h",
                    "commit_sha": "abc123def456",
                    "line_hint": "outline",
                    "slice_id": "abc123def456:include__linux__llist.h:outline",
                    "content": "Changed symbols: llist_for_each_entry",
                },
                "snapshot": "",
                "snapshot_error": None,
            }
        ],
        "digest_contexts": [
            {
                "file_path": "include/linux/llist.h",
                "primary_symbol": "llist_for_each_entry",
                "changed_symbols": [
                    "llist_for_each_entry",
                    "member_address_is_nonnull",
                ],
                "summary": "File: include/linux/llist.h\nChanged symbols: llist_for_each_entry, member_address_is_nonnull",
                "code_contexts": [],
                "patch_preview": "@@ -1,2 +1,2 @@",
            }
        ],
    }


class FakeDigestor:
    def run(self, state):
        return {
            "previous_issue": "The loop condition becomes always true under Clang.",
            "patching_purpose": "Replace the member-address null check with an integer-based helper.",
            "compiler_behavior": "Clang treats &pos->member as non-null and optimizes the loop into an infinite loop.",
            "function_contexts": [
                {
                    "file_path": "include/linux/llist.h",
                    "primary_symbol": "llist_for_each_entry",
                    "changed_symbols": ["llist_for_each_entry", "member_address_is_nonnull"],
                    "why_it_matters": "The loop guard is patched here.",
                    "code_summary": "Changed symbols: llist_for_each_entry, member_address_is_nonnull",
                }
            ],
            "focused_contexts": [
                {
                    "file_path": "include/linux/llist.h",
                    "slice_id": "abc123def456:include__linux__llist.h:focus:0",
                    "reason": "The loop guard is patched here.",
                }
            ],
            "uncertainties": [],
        }


class FakeLibrarian:
    def ask(self, question):
        return {
            "source_type": "knowledge",
            "file_path": None,
            "commit_sha": None,
            "line_hint": "knowledge",
            "slice_id": "librarian",
            "content": f"Knowledge answer for: {question}",
            "citations": ["concept_distinctions.md > Default Behavior"],
            "coverage_note": "Covered.",
        }


class LoopReasoner:
    def next_action(self, state):
        return {"action": "get_commit_overview"}


class AnsweringReasoner:
    def __init__(self):
        self.index = 0
        self.actions = [
            {
                "action": "answer_question",
                "question_id": "q1",
                "answer": "yes",
                "reason": "first answer",
            },
            {
                "action": "answer_question",
                "question_id": "q2",
                "answer": "no",
                "reason": "second answer",
            },
            {
                "action": "submit_to_judge",
                "summary": "completed",
            },
        ]

    def next_action(self, state):
        action = self.actions[self.index]
        self.index += 1
        return action


class FakeJudge:
    def run(self, state):
        return {
            "title": "loop fix",
            "issue": state.digest["previous_issue"],
            "tag": "kernel runtime fix",
            "purpose": state.digest["patching_purpose"],
            "step_analysis": {
                "key_variables_functionality": "Loop cursor and member address check.",
                "compiler_behavior": state.digest["compiler_behavior"],
                "pre_post_compilation": "Loop becomes infinite after compilation.",
                "security_implications": "Potential denial of service.",
            },
            "binary_answers": {
                question_id: {"answer": "no", "reason": "stub"}
                for question_id in QUESTION_TEXT
            },
            "cisb_status": "no",
            "spec": {
                "trigger_condition": "",
                "broken_security_property": "",
                "compiler_behavior": "",
                "affected_code_pattern": "",
                "evidence": [],
            },
        }


class AgenticKernelTests(unittest.TestCase):
    def test_validate_reasoner_action_rejects_invalid_tool(self):
        with self.assertRaises(ValueError):
            validate_reasoner_action({"action": "unknown_tool"})

    def test_record_evidence_uses_last_observation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = KernelRunState(
                commit_id="abc123def456",
                raw_report={"id": "abc123def456"},
                cache=make_cache(),
                cache_path=os.path.join(tmpdir, "abc123def456.json"),
                output_dir=tmpdir,
            )
            tools = KernelToolRegistry(state, FakeLibrarian())

            tools.execute(
                {
                    "action": "get_focus_slice",
                    "file_path": "include/linux/llist.h",
                    "slice_id": "abc123def456:include__linux__llist.h:focus:0",
                }
            )
            tools.execute(
                {
                    "action": "record_evidence",
                    "question_id": "q3",
                    "note": "This slice shows the compiler-sensitive loop guard.",
                }
            )

            self.assertEqual(len(state.evidence_ledger["q3"]), 1)
            self.assertEqual(
                state.evidence_ledger["q3"][0]["slice_id"],
                "abc123def456:include__linux__llist.h:focus:0",
            )
            self.assertEqual(state.last_observation["tool"], "get_focus_slice")

    def test_duplicate_focus_slice_returns_dedup_notice(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = KernelRunState(
                commit_id="abc123def456",
                raw_report={"id": "abc123def456"},
                cache=make_cache(),
                cache_path=os.path.join(tmpdir, "abc123def456.json"),
                output_dir=tmpdir,
            )
            tools = KernelToolRegistry(state, FakeLibrarian())

            first = tools.execute(
                {
                    "action": "get_focus_slice",
                    "file_path": "include/linux/llist.h",
                    "slice_id": "abc123def456:include__linux__llist.h:focus:0",
                }
            )
            duplicate = tools.execute(
                {
                    "action": "get_focus_slice",
                    "file_path": "include/linux/llist.h",
                    "slice_id": "abc123def456:include__linux__llist.h:focus:0",
                }
            )

            self.assertEqual(first["source_type"], "focus_slice")
            self.assertEqual(duplicate["source_type"], "duplicate_focus_slice")
            self.assertIn("already inspected", duplicate["content"])
            self.assertIn("focus:1", duplicate["content"])
            self.assertEqual(
                state.last_observation["slice_id"],
                "abc123def456:include__linux__llist.h:focus:0",
            )

    def test_build_initial_impression_populates_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = KernelRunState(
                commit_id="abc123def456",
                raw_report={"id": "abc123def456"},
                cache=make_cache(),
                cache_path=os.path.join(tmpdir, "abc123def456.json"),
                output_dir=tmpdir,
                digest=FakeDigestor().run(None),
            )
            tools = KernelToolRegistry(state, FakeLibrarian())

            result = tools.execute({"action": "build_initial_impression"})

            self.assertEqual(result["source_type"], "initial_impression")
            self.assertTrue(state.initial_impression["content"].startswith("Knowledge answer for:"))
            self.assertEqual(state.last_observation["source_type"], "initial_impression")

    def test_review_digest_context_returns_digest_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = KernelRunState(
                commit_id="abc123def456",
                raw_report={"id": "abc123def456"},
                cache=make_cache(),
                cache_path=os.path.join(tmpdir, "abc123def456.json"),
                output_dir=tmpdir,
                digest=FakeDigestor().run(None),
            )
            tools = KernelToolRegistry(state, FakeLibrarian())

            result = tools.execute(
                {
                    "action": "review_digest_context",
                    "file_path": "include/linux/llist.h",
                }
            )

            self.assertEqual(result["source_type"], "digest_context")
            self.assertIn("Changed symbols:", result["content"])
            self.assertEqual(state.last_observation["source_type"], "digest_context")

    def test_unknown_focus_slice_falls_back_to_cached_slice(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = KernelRunState(
                commit_id="abc123def456",
                raw_report={"id": "abc123def456"},
                cache=make_cache(),
                cache_path=os.path.join(tmpdir, "abc123def456.json"),
                output_dir=tmpdir,
            )
            tools = KernelToolRegistry(state, FakeLibrarian())

            result = tools.execute(
                {
                    "action": "get_focus_slice",
                    "file_path": "include/linux/llist.h",
                    "slice_id": "abc123def456:include__linux__llist.h:focus:9",
                }
            )

            self.assertEqual(result["source_type"], "focus_slice")
            self.assertEqual(
                result["slice_id"],
                "abc123def456:include__linux__llist.h:focus:0",
            )
            self.assertIn("Requested slice_id", result["content"])

    def test_digestor_heuristic_includes_function_contexts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = make_cache()
            cache["digest_contexts"] = [
                {
                    "file_path": "include/linux/llist.h",
                    "primary_symbol": "llist_for_each_entry",
                    "changed_symbols": ["llist_for_each_entry", "member_address_is_nonnull"],
                    "summary": "File: include/linux/llist.h\nChanged symbols: llist_for_each_entry, member_address_is_nonnull",
                    "code_contexts": [],
                    "patch_preview": "@@ ...",
                }
            ]
            state = KernelRunState(
                commit_id="abc123def456",
                raw_report={"id": "abc123def456"},
                cache=cache,
                cache_path=os.path.join(tmpdir, "abc123def456.json"),
                output_dir=tmpdir,
            )
            digestor = DigestorAgent(None, None, None)
            digest = digestor.run(state)

            self.assertEqual(len(digest["function_contexts"]), 1)
            self.assertEqual(
                digest["function_contexts"][0]["primary_symbol"],
                "llist_for_each_entry",
            )
            self.assertIn(
                "Changed symbols:",
                digest["function_contexts"][0]["code_summary"],
            )

    def test_orchestrator_stops_at_stall_limit(self):
        seed_report = {
            "id": "abc123def456",
            "year": "2017",
            "message": "llist: fix compiler-induced infinite loop\n\nClang assumes member address is non-null.",
            "patches": {"include/linux/llist.h": "@@ -1,2 +1,2 @@\n- old\n+ new\n"},
        }

        class NoNetworkScheduler:
            def fetch_commit_info(self, commit_sha):
                raise RuntimeError("offline")

            def fetch_file_snapshot(self, commit_sha, file_path):
                raise RuntimeError("offline")

        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = AgenticKernelOrchestrator(
                None,
                None,
                None,
                None,
                None,
                None,
                output_dir=tmpdir,
                cache_dir=os.path.join(tmpdir, "cache"),
                cache_policy={"fetch_snapshots": False},
                scheduler=NoNetworkScheduler(),
                digestor_agent=FakeDigestor(),
                librarian_agent=FakeLibrarian(),
                reasoner_agent=LoopReasoner(),
                judge_agent=FakeJudge(),
                max_steps=2,
            )

            state = orchestrator.run("abc123def456", seed_report=seed_report, persist=False)

            self.assertEqual(state.termination_reason, "stall_limit")
            self.assertEqual(len(state.tool_history), 2)
            self.assertEqual(state.final_decision["cisb_status"], "no")

    def test_answer_question_progress_does_not_trigger_stall_limit(self):
        seed_report = {
            "id": "abc123def456",
            "year": "2017",
            "message": "llist: fix compiler-induced infinite loop\n\nClang assumes member address is non-null.",
            "patches": {"include/linux/llist.h": "@@ -1,2 +1,2 @@\n- old\n+ new\n"},
        }

        class NoNetworkScheduler:
            def fetch_commit_info(self, commit_sha):
                raise RuntimeError("offline")

            def fetch_file_snapshot(self, commit_sha, file_path):
                raise RuntimeError("offline")

        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = AgenticKernelOrchestrator(
                None,
                None,
                None,
                None,
                None,
                None,
                output_dir=tmpdir,
                cache_dir=os.path.join(tmpdir, "cache"),
                cache_policy={"fetch_snapshots": False},
                scheduler=NoNetworkScheduler(),
                digestor_agent=FakeDigestor(),
                librarian_agent=FakeLibrarian(),
                reasoner_agent=AnsweringReasoner(),
                judge_agent=FakeJudge(),
                max_steps=1,
                total_action_limit=5,
            )

            state = orchestrator.run("abc123def456", seed_report=seed_report, persist=False)

            self.assertEqual(state.termination_reason, "completed")
            self.assertEqual(state.question_answers["q1"]["answer"], "yes")
            self.assertEqual(state.question_answers["q2"]["answer"], "no")


if __name__ == "__main__":
    unittest.main()
