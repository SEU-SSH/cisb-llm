import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agent import Agent
from agentic_prompts import (
    DIGESTOR_PROMPT,
    JUDGE_PROMPT,
    LIBRARIAN_PROMPT,
    REASONER_PROMPT,
)
from helper import Helper


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kernel_api import DEFAULT_CACHE_DIR, KernelApiScheduler, prepare_commit_cache


QUESTION_TEXT = {
    "q1": "Did compiler accept the kernel code and compile it successfully?",
    "q2": "Is the commit describing a runtime bug caused by optimization or default compiler behavior?",
    "q3": "Without that optimization or default behavior, would the problematic difference disappear?",
    "q4": "Did observable runtime behavior change after compilation?",
    "q5": "Does the change have direct or indirect security implications in kernel context?",
}
TOOL_NAMES = {
    "build_initial_impression",
    "review_digest_context",
    "get_commit_overview",
    "list_changed_files",
    "get_patch_for_file",
    "get_focus_slice",
    "get_file_outline",
    "query_librarian",
    "record_evidence",
}
ACTION_NAMES = TOOL_NAMES | {"answer_question", "submit_to_judge"}


def _default_question_answers():
    return {}


def _default_evidence_ledger():
    return {question_id: [] for question_id in QUESTION_TEXT}


def _trim_text(text, limit=1600):
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 5] + "\n..."


def normalize_answer(answer):
    answer = (answer or "unknown").strip().lower()
    if answer not in {"yes", "no", "unknown"}:
        raise ValueError(f"Unsupported answer value: {answer}")
    return answer


def validate_reasoner_action(payload):
    if not isinstance(payload, dict):
        raise ValueError("Reasoner action must be a JSON object.")

    action = payload.get("action")
    if action not in ACTION_NAMES:
        raise ValueError(f"Unsupported reasoner action: {action}")

    if action in {"build_initial_impression", "review_digest_context"}:
        return payload

    if action in {"get_patch_for_file", "get_focus_slice", "get_file_outline"}:
        if not payload.get("file_path"):
            raise ValueError(f"{action} requires file_path.")

    if action == "query_librarian":
        if not payload.get("question"):
            raise ValueError("query_librarian requires question.")
        if payload.get("question_id") not in QUESTION_TEXT:
            raise ValueError("query_librarian requires a valid question_id.")

    if action == "record_evidence":
        if payload.get("question_id") not in QUESTION_TEXT:
            raise ValueError("record_evidence requires a valid question_id.")

    if action == "answer_question":
        if payload.get("question_id") not in QUESTION_TEXT:
            raise ValueError("answer_question requires a valid question_id.")
        normalize_answer(payload.get("answer"))
        if not payload.get("reason"):
            raise ValueError("answer_question requires reason.")

    if action == "submit_to_judge" and not payload.get("summary"):
        raise ValueError("submit_to_judge requires summary.")

    return payload


def summarize_evidence(items, limit=3):
    lines = []
    for item in items[:limit]:
        source = item.get("source_type")
        path = item.get("file_path") or "knowledge"
        hint = item.get("line_hint") or item.get("citation") or ""
        lines.append(f"- {source} {path} {hint}: {_trim_text(item.get('content', ''), 220)}")
    return "\n".join(lines) if lines else "No recorded evidence."


def build_initial_impression_question(digest):
    return (
        "Explain what CISB means for this kernel commit and which concept distinctions "
        "or constraints matter most before reasoning.\n"
        f"previous issue: {digest.get('previous_issue', '')}\n"
        f"patching purpose: {digest.get('patching_purpose', '')}\n"
        f"compiler behavior: {digest.get('compiler_behavior', '')}\n"
        "Focus on developer expectation, compiler assumption/default behavior, "
        "and possible security relevance."
    )


def determine_reasoning_stage(state):
    if not state.initial_impression:
        return {
            "stage": "initial_impression",
            "instruction": "Build the CISB framing first by calling build_initial_impression.",
        }

    if not state.evidence_ledger["q1"] and not state.question_answers.get("q1"):
        return {
            "stage": "key_functionality",
            "instruction": "Use review_digest_context to identify the key variables, functions, and affected semantics.",
        }

    if not state.question_answers.get("q2") or not state.question_answers.get("q3"):
        return {
            "stage": "compiler_behavior",
            "instruction": "Reason about the optimization/default behavior and ask Librarian first if CISB concepts or distinctions are unclear.",
        }

    if not state.question_answers.get("q4"):
        return {
            "stage": "pre_post_compilation",
            "instruction": "Contrast intended functionality against post-compilation behavior.",
        }

    if not state.question_answers.get("q5"):
        return {
            "stage": "security_implications",
            "instruction": "Evaluate direct or indirect security implications in kernel context. Query Librarian first if you need concept support.",
        }

    return {
        "stage": "finalize",
        "instruction": "All major reasoning stages are covered. Finalize remaining answers and submit to Judge.",
    }


@dataclass
class KernelRunState:
    commit_id: str
    raw_report: dict
    cache: dict
    cache_path: str
    output_dir: str
    max_steps: int = 12
    total_action_limit: int = 40
    max_invalid_actions: int = 3
    digest: dict = field(default_factory=dict)
    evidence_ledger: dict = field(default_factory=_default_evidence_ledger)
    question_answers: dict = field(default_factory=_default_question_answers)
    tool_history: list = field(default_factory=list)
    reasoning_history: list = field(default_factory=list)
    librarian_history: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    last_observation: dict = field(default_factory=dict)
    termination_reason: str = ""
    final_decision: dict = field(default_factory=dict)
    action_count: int = 0
    stall_count: int = 0
    initial_impression: dict = field(default_factory=dict)

    def recent_tool_history(self, limit=4):
        return self.tool_history[-limit:]

    def to_trace(self):
        return {
            "commit_id": self.commit_id,
            "cache_path": self.cache_path,
            "digest": self.digest,
            "tool_history": self.tool_history,
            "reasoning_history": self.reasoning_history,
            "librarian_history": self.librarian_history,
            "evidence_ledger": self.evidence_ledger,
            "question_answers": self.question_answers,
            "initial_impression": self.initial_impression,
            "termination_reason": self.termination_reason,
            "errors": self.errors,
            "action_count": self.action_count,
            "stall_count": self.stall_count,
            "stall_limit": self.max_steps,
            "total_action_limit": self.total_action_limit,
            "final_decision": {
                "title": self.final_decision.get("title"),
                "cisb_status": self.final_decision.get("cisb_status"),
                "tag": self.final_decision.get("tag"),
            },
        }


@dataclass
class EvidenceItem:
    question_id: str
    source_type: str
    commit_sha: str
    file_path: str = None
    line_hint: str = None
    slice_id: str = None
    content: str = ""
    note: str = ""
    citation: str = None

    def to_dict(self):
        return asdict(self)


class KernelAgent(Agent):
    def __init__(self, model, prompt, api_key, url, platform="kernel"):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.API_KEY = api_key
        self.URL = url
        self.platform = platform

    def can_call_model(self):
        return bool(self.model and self.API_KEY and self.URL)

    def call_json(self, payload, temperature=0.2, max_tokens=3072):
        text = self.complete_chat(
            [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            json_mode=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self.extract_json_payload(text)


class DigestorAgent(KernelAgent):
    def __init__(self, model, api_key, url):
        super().__init__(model, DIGESTOR_PROMPT, api_key, url)

    def _heuristic_digest(self, state):
        message = state.cache.get("message", "")
        files = state.cache.get("files", [])
        digest_contexts = state.cache.get("digest_contexts", [])
        contexts = []
        function_contexts = []
        uncertainties = []

        for file_entry in files[:2]:
            focus_slices = file_entry.get("focus_slices", [])
            if not focus_slices:
                uncertainties.append(f"No focus slice available for {file_entry.get('file_path')}.")
                continue
            contexts.append(
                {
                    "file_path": file_entry.get("file_path"),
                    "slice_id": focus_slices[0].get("slice_id"),
                    "reason": "Top-priority changed file selected from cached focus slices.",
                }
            )
            if file_entry.get("snapshot_error"):
                uncertainties.append(
                    f"Snapshot unavailable for {file_entry.get('file_path')}: {file_entry.get('snapshot_error')}"
                )

        for digest_context in digest_contexts[:3]:
            function_contexts.append(
                {
                    "file_path": digest_context.get("file_path"),
                    "primary_symbol": digest_context.get("primary_symbol"),
                    "changed_symbols": digest_context.get("changed_symbols", []),
                    "why_it_matters": "This file/function is touched by the diff and selected as high-priority context.",
                    "code_summary": digest_context.get("summary", ""),
                }
            )

        message_lines = [line.strip() for line in message.splitlines() if line.strip()]
        compiler_lines = [
            line
            for line in message_lines
            if any(
                token in line.lower()
                for token in ("compiler", "clang", "gcc", "optimi", "nonnull", "inline")
            )
        ]

        return {
            "previous_issue": message_lines[1] if len(message_lines) > 1 else (message_lines[0] if message_lines else ""),
            "patching_purpose": message_lines[0] if message_lines else "",
            "compiler_behavior": " ".join(compiler_lines[:2]),
            "function_contexts": function_contexts,
            "focused_contexts": contexts,
            "uncertainties": uncertainties,
        }

    def run(self, state):
        digest_context_preview = []
        for digest_context in state.cache.get("digest_contexts", [])[:3]:
            digest_context_preview.append(
                {
                    "file_path": digest_context.get("file_path"),
                    "primary_symbol": digest_context.get("primary_symbol"),
                    "changed_symbols": digest_context.get("changed_symbols", []),
                    "summary": digest_context.get("summary", ""),
                    "code_contexts": [
                        {
                            "slice_id": entry.get("slice_id"),
                            "line_hint": entry.get("line_hint"),
                            "header": entry.get("header"),
                            "content": _trim_text(entry.get("content", ""), 900),
                        }
                        for entry in digest_context.get("code_contexts", [])[:2]
                    ],
                    "patch_preview": _trim_text(digest_context.get("patch_preview", ""), 800),
                }
            )

        payload = {
            "overview": state.cache.get("overview", {}),
            "priority_files": state.cache.get("prioritized_files", []),
            "digest_context_preview": digest_context_preview,
        }

        if not self.can_call_model():
            return self._heuristic_digest(state)

        try:
            digest = self.call_json(payload, max_tokens=3200)
        except Exception as exc:
            state.errors.append(f"Digestor fallback: {exc}")
            return self._heuristic_digest(state)

        fallback = self._heuristic_digest(state)
        return {
            "previous_issue": digest.get("previous_issue", fallback["previous_issue"]),
            "patching_purpose": digest.get("patching_purpose", fallback["patching_purpose"]),
            "compiler_behavior": digest.get("compiler_behavior", fallback["compiler_behavior"]),
            "function_contexts": digest.get("function_contexts") or fallback["function_contexts"],
            "focused_contexts": digest.get("focused_contexts") or fallback["focused_contexts"],
            "uncertainties": digest.get("uncertainties") or fallback["uncertainties"],
        }


class LibrarianAgent(KernelAgent):
    def __init__(self, model, api_key, url, retriever=None, top_k=3):
        super().__init__(model, LIBRARIAN_PROMPT, api_key, url)
        self.retriever = retriever
        self.top_k = top_k

    def _heuristic_answer(self, question, entries):
        citations = []
        answer_parts = []
        for entry in entries[:2]:
            citation = f"{entry.get('source')} > {entry.get('header')}"
            citations.append(citation)
            answer_parts.append(_trim_text(entry.get("content", ""), 220))

        coverage = "Retrieved knowledge snippets cover the question." if entries else "No relevant knowledge retrieved."
        return {
            "answer": "\n\n".join(answer_parts) if answer_parts else f"No retrieved knowledge for: {question}",
            "citations": citations,
            "coverage_note": coverage,
        }

    def ask(self, question):
        entries = []
        if self.retriever is not None:
            try:
                entries = self.retriever.retrieve(question, top_k=self.top_k)
            except Exception as exc:
                entries = []
                coverage_note = f"Retriever unavailable: {exc}"
            else:
                coverage_note = ""
        else:
            coverage_note = "Retriever unavailable."

        if not self.can_call_model() or not entries:
            response = self._heuristic_answer(question, entries)
        else:
            try:
                response = self.call_json(
                    {
                        "question": question,
                        "references": [
                            {
                                "source": entry.get("source"),
                                "header": entry.get("header"),
                                "content": _trim_text(entry.get("content", ""), 450),
                            }
                            for entry in entries
                        ],
                    },
                    max_tokens=1200,
                )
            except Exception:
                response = self._heuristic_answer(question, entries)

        if coverage_note:
            response["coverage_note"] = (
                f"{response.get('coverage_note', '').strip()} {coverage_note}".strip()
            )

        return {
            "source_type": "knowledge",
            "file_path": None,
            "commit_sha": None,
            "line_hint": "knowledge",
            "slice_id": "librarian",
            "content": response.get("answer", ""),
            "citations": response.get("citations", []),
            "coverage_note": response.get("coverage_note", ""),
            "retrieved_entries": entries,
        }


class ReasonerAgent(KernelAgent):
    def __init__(self, model, api_key, url):
        super().__init__(model, REASONER_PROMPT, api_key, url)

    def _heuristic_answer(self, question_id, state):
        message = (state.cache.get("message") or "").lower()
        compiler_behavior = (state.digest.get("compiler_behavior") or "").lower()
        initial_impression = (state.initial_impression.get("content") or "").lower()
        security_text = " ".join(
            item.get("content", "")
            for item in state.evidence_ledger.get("q5", [])
        ).lower()

        if question_id == "q1":
            return "yes", "The commit discusses a post-compilation runtime issue rather than a syntax rejection."
        if question_id == "q2":
            answer = "yes" if any(token in message + " " + initial_impression for token in ("compiler", "clang", "gcc", "optimi")) else "unknown"
            reason = state.digest.get("compiler_behavior") or state.initial_impression.get("content") or "The commit message does not clearly state a compiler-induced runtime bug."
            return answer, reason
        if question_id == "q3":
            answer = "yes" if compiler_behavior or initial_impression else "unknown"
            reason = state.digest.get("compiler_behavior") or state.initial_impression.get("content") or "No clear optimization/default-behavior description was extracted."
            return answer, reason
        if question_id == "q4":
            answer = "yes" if any(token in message for token in ("infinite", "hang", "crash", "wrong", "leak", "overflow")) else "unknown"
            reason = state.digest.get("previous_issue") or "Observable runtime change is not explicit in the cached summary."
            return answer, reason
        if question_id == "q5":
            dangerous = any(token in message + " " + security_text + " " + initial_impression for token in ("security", "leak", "overflow", "memory", "bypass", "infinite", "verifier"))
            answer = "yes" if dangerous else "unknown"
            reason = state.initial_impression.get("content") if dangerous and state.initial_impression else ("Security-relevant keywords appear in the message or evidence." if dangerous else "Security implications are not explicit in the currently cached evidence.")
            return answer, reason
        return "unknown", "No heuristic answer available."

    def _heuristic_next_action(self, state):
        if not state.initial_impression:
            return {"action": "build_initial_impression"}

        if state.digest.get("function_contexts") and state.last_observation.get("source_type") != "digest_context":
            return {
                "action": "review_digest_context",
                "file_path": state.digest["function_contexts"][0].get("file_path"),
            }

        if state.digest.get("compiler_behavior") and not state.librarian_history:
            return {
                "action": "query_librarian",
                "question_id": "q3",
                "question": state.digest.get("compiler_behavior"),
            }

        if state.last_observation and not state.evidence_ledger["q3"]:
            return {
                "action": "record_evidence",
                "question_id": "q3",
                "note": "Captured the digest-derived observation as compiler-behavior evidence.",
            }

        for question_id in QUESTION_TEXT:
            if question_id not in state.question_answers:
                answer, reason = self._heuristic_answer(question_id, state)
                return {
                    "action": "answer_question",
                    "question_id": question_id,
                    "answer": answer,
                    "reason": reason,
                }

        return {
            "action": "submit_to_judge",
            "summary": "Heuristic fallback completed the reasoning loop.",
        }

    def next_action(self, state):
        if not self.can_call_model():
            return validate_reasoner_action(self._heuristic_next_action(state))

        digest_contexts = state.digest.get("function_contexts") or []
        available_tools = [
            "build_initial_impression",
            "review_digest_context",
            "query_librarian",
            "record_evidence",
            "answer_question",
            "submit_to_judge",
        ]
        if state.digest.get("uncertainties"):
            available_tools.extend(["get_patch_for_file", "get_file_outline"])

        payload = {
            "commit_overview": state.cache.get("overview", {}).get("content", ""),
            "digest": state.digest,
            "digest_contexts": digest_contexts,
            "initial_impression": state.initial_impression,
            "reasoning_stage": determine_reasoning_stage(state),
            "pending_questions": [
                question_id
                for question_id in QUESTION_TEXT
                if question_id not in state.question_answers
            ],
            "question_answers": state.question_answers,
            "evidence_counts": {
                question_id: len(items)
                for question_id, items in state.evidence_ledger.items()
            },
            "last_observation": {
                key: value
                for key, value in state.last_observation.items()
                if key in {"tool", "source_type", "file_path", "line_hint", "slice_id", "content", "citations"}
            },
            "recent_tool_history": state.recent_tool_history(),
            "available_tools": available_tools,
        }

        try:
            action = self.call_json(payload, max_tokens=1600)
        except Exception as exc:
            state.errors.append(f"Reasoner fallback: {exc}")
            return validate_reasoner_action(self._heuristic_next_action(state))

        return validate_reasoner_action(action)


class JudgeAgent(KernelAgent):
    def __init__(self, model, api_key, url):
        super().__init__(model, JUDGE_PROMPT, api_key, url)

    def _heuristic_decision(self, state):
        answers = {}
        for question_id in QUESTION_TEXT:
            if question_id in state.question_answers:
                answers[question_id] = state.question_answers[question_id]
                continue
            answer, reason = ReasonerAgent(None, None, None)._heuristic_answer(question_id, state)
            answers[question_id] = {"answer": answer, "reason": reason}

        cisb_status = (
            "yes"
            if all(item.get("answer") == "yes" for item in answers.values())
            else "no"
        )

        step_analysis = {
            "key_variables_functionality": summarize_evidence(state.evidence_ledger.get("q2", []) or state.evidence_ledger.get("q3", [])),
            "compiler_behavior": state.digest.get("compiler_behavior") or summarize_evidence(state.evidence_ledger.get("q3", [])),
            "pre_post_compilation": answers["q4"]["reason"],
            "security_implications": answers["q5"]["reason"],
        }

        spec = {
            "trigger_condition": state.digest.get("previous_issue", ""),
            "broken_security_property": answers["q5"]["reason"],
            "compiler_behavior": state.digest.get("compiler_behavior", ""),
            "affected_code_pattern": ", ".join(
                context.get("file_path", "")
                for context in state.digest.get("focused_contexts", [])
            ),
            "evidence": [
                item.get("note") or item.get("content", "")
                for items in state.evidence_ledger.values()
                for item in items[:1]
            ][:5],
        }

        title = ""
        raw_message = state.raw_report.get("message", "") if state.raw_report else ""
        cache_message = state.cache.get("message", "")
        for candidate in (raw_message, cache_message):
            if candidate:
                lines = candidate.splitlines()
                if lines:
                    title = lines[0]
                    break
        if not title:
            title = f"kernel commit {state.commit_id}"

        return {
            "title": title,
            "issue": state.digest.get("previous_issue", ""),
            "tag": "potential CISB" if cisb_status == "yes" else "kernel runtime fix",
            "purpose": state.digest.get("patching_purpose", ""),
            "step_analysis": step_analysis,
            "binary_answers": answers,
            "cisb_status": cisb_status,
            "spec": spec,
        }

    def run(self, state):
        payload = {
            "digest": state.digest,
            "evidence_ledger": state.evidence_ledger,
            "question_answers": state.question_answers,
            "commit_overview": state.cache.get("overview", {}).get("content", ""),
            "termination_reason": state.termination_reason,
        }

        if not self.can_call_model():
            return self._heuristic_decision(state)

        try:
            decision = self.call_json(payload, max_tokens=3600)
        except Exception as exc:
            state.errors.append(f"Judge fallback: {exc}")
            return self._heuristic_decision(state)

        fallback = self._heuristic_decision(state)
        decision.setdefault("binary_answers", fallback["binary_answers"])
        decision.setdefault("step_analysis", fallback["step_analysis"])
        decision.setdefault("tag", fallback["tag"])
        decision.setdefault("purpose", fallback["purpose"])
        decision.setdefault("issue", fallback["issue"])
        decision.setdefault("title", fallback["title"])
        decision.setdefault("cisb_status", fallback["cisb_status"])
        decision.setdefault("spec", fallback["spec"])
        return decision


class KernelToolRegistry:
    def __init__(self, state, librarian):
        self.state = state
        self.librarian = librarian
        self.file_map = {
            entry.get("file_path"): entry for entry in self.state.cache.get("files", [])
        }

    def _get_file(self, file_path):
        if file_path not in self.file_map:
            raise ValueError(f"Unknown file path requested: {file_path}")
        return self.file_map[file_path]

    def _get_digest_context(self, file_path=None):
        contexts = self.state.digest.get("function_contexts") or []
        if not contexts:
            raise ValueError("No digest contexts are available for review.")
        if file_path:
            for context in contexts:
                if context.get("file_path") == file_path:
                    return dict(context)
        return dict(contexts[0])

    def _find_prior_focus_access(self, slice_id):
        for entry in self.state.tool_history:
            if (
                entry.get("action") == "get_focus_slice"
                and entry.get("result", {}).get("slice_id") == slice_id
                and entry.get("result", {}).get("source_type") == "focus_slice"
            ):
                return entry
        return None

    def _pick_focus_slice(self, focus_slices, requested_slice_id=None):
        if requested_slice_id:
            for focus_slice in focus_slices:
                if focus_slice.get("slice_id") == requested_slice_id:
                    return dict(focus_slice), None

        for focus_slice in focus_slices:
            if not self._find_prior_focus_access(focus_slice.get("slice_id")):
                if requested_slice_id and focus_slice.get("slice_id") != requested_slice_id:
                    warning = (
                        f"Requested slice_id {requested_slice_id} was not cached. "
                        f"Fell back to {focus_slice.get('slice_id')}."
                    )
                else:
                    warning = None
                return dict(focus_slice), warning

        fallback = dict(focus_slices[0])
        if requested_slice_id and fallback.get("slice_id") != requested_slice_id:
            warning = (
                f"Requested slice_id {requested_slice_id} was not cached. "
                f"Fell back to {fallback.get('slice_id')}."
            )
        else:
            warning = None
        return fallback, warning

    def _build_duplicate_focus_result(self, selected_slice, focus_slices, fallback_warning=None):
        prior_access = self._find_prior_focus_access(selected_slice.get("slice_id"))
        available_alternatives = [
            focus_slice.get("slice_id")
            for focus_slice in focus_slices
            if focus_slice.get("slice_id") != selected_slice.get("slice_id")
        ]

        lines = []
        if fallback_warning:
            lines.append(fallback_warning)
        if prior_access is not None:
            lines.append(
                f"Slice {selected_slice.get('slice_id')} was already inspected at tool step {prior_access.get('step')}."
            )
        else:
            lines.append(
                f"Slice {selected_slice.get('slice_id')} was already inspected earlier in this run."
            )
        if available_alternatives:
            lines.append(
                "Try a different cached slice for this file: "
                + ", ".join(available_alternatives[:2])
            )
        else:
            lines.append(
                "No alternate focus slices are cached for this file. "
                "Use get_patch_for_file, get_file_outline, record_evidence, or answer_question."
            )

        return {
            "source_type": "duplicate_focus_slice",
            "file_path": selected_slice.get("file_path"),
            "commit_sha": self.state.commit_id,
            "line_hint": selected_slice.get("line_hint"),
            "slice_id": selected_slice.get("slice_id"),
            "content": " ".join(lines),
        }

    def _remember(self, action_name, action, result, update_last_observation=True):
        result = dict(result)
        history_entry = {
            "step": len(self.state.tool_history) + 1,
            "action": action_name,
            "parameters": {
                key: value
                for key, value in action.items()
                if key != "action"
            },
            "result": {
                "source_type": result.get("source_type"),
                "file_path": result.get("file_path"),
                "line_hint": result.get("line_hint"),
                "slice_id": result.get("slice_id"),
                "content": _trim_text(result.get("content", ""), 260),
            },
        }
        self.state.tool_history.append(history_entry)
        if update_last_observation:
            result["tool"] = action_name
            self.state.last_observation = result
        return result

    def execute(self, action):
        action_name = action["action"]

        if action_name == "build_initial_impression":
            question = build_initial_impression_question(self.state.digest)
            already_built = bool(self.state.initial_impression)
            result = self.librarian.ask(question)
            impression_result = {
                "source_type": "initial_impression",
                "file_path": None,
                "commit_sha": self.state.commit_id,
                "line_hint": "initial_impression",
                "slice_id": "initial_impression",
                "content": result.get("content", ""),
                "citations": result.get("citations", []),
                "coverage_note": result.get("coverage_note"),
                "_progress": not already_built,
            }
            self.state.initial_impression = {
                "question": question,
                "content": result.get("content", ""),
                "citations": result.get("citations", []),
                "coverage_note": result.get("coverage_note"),
            }
            self.state.librarian_history.append(
                {
                    "question_id": "initial_impression",
                    "question": question,
                    "answer": _trim_text(result.get("content", ""), 260),
                    "citations": result.get("citations", []),
                    "coverage_note": result.get("coverage_note"),
                }
            )
            return self._remember(action_name, action, impression_result)

        if action_name == "review_digest_context":
            digest_context = self._get_digest_context(action.get("file_path"))
            result = {
                "source_type": "digest_context",
                "file_path": digest_context.get("file_path"),
                "commit_sha": self.state.commit_id,
                "line_hint": "digest_context",
                "slice_id": digest_context.get("primary_symbol") or digest_context.get("file_path"),
                "content": _trim_text(
                    digest_context.get("code_summary", "")
                    + "\n"
                    + "Changed symbols: "
                    + ", ".join(digest_context.get("changed_symbols", [])),
                    1800,
                ),
                "_progress": False,
            }
            return self._remember(action_name, action, result)

        if action_name == "get_commit_overview":
            result = dict(self.state.cache.get("overview", {}))
            result["_progress"] = False
            return self._remember(action_name, action, result)

        if action_name == "list_changed_files":
            lines = []
            for file_entry in sorted(
                self.state.cache.get("files", []),
                key=lambda entry: (entry.get("priority_rank") or 999, entry.get("file_path")),
            ):
                lines.append(
                    f"{file_entry.get('priority_rank') or '-'} | {file_entry.get('file_path')} | changes={file_entry.get('changes')}"
                )
            result = {
                "source_type": "changed_files",
                "file_path": None,
                "commit_sha": self.state.commit_id,
                "line_hint": "files",
                "slice_id": f"{self.state.commit_id}:files",
                "content": "\n".join(lines),
                "_progress": False,
            }
            return self._remember(action_name, action, result)

        if action_name == "get_patch_for_file":
            file_entry = self._get_file(action["file_path"])
            result = {
                "source_type": "patch_hunk",
                "file_path": file_entry.get("file_path"),
                "commit_sha": self.state.commit_id,
                "line_hint": "patch",
                "slice_id": f"{self.state.commit_id}:{file_entry.get('file_path')}:patch",
                "content": _trim_text(file_entry.get("patch", ""), 1800),
                "_progress": False,
            }
            return self._remember(action_name, action, result)

        if action_name == "get_focus_slice":
            file_entry = self._get_file(action["file_path"])
            focus_slices = file_entry.get("focus_slices", [])
            if not focus_slices:
                raise ValueError(f"No focus slices prepared for {action['file_path']}.")
            selected_slice, fallback_warning = self._pick_focus_slice(
                focus_slices,
                requested_slice_id=action.get("slice_id"),
            )
            if self._find_prior_focus_access(selected_slice.get("slice_id")):
                duplicate_result = self._build_duplicate_focus_result(
                    selected_slice,
                    focus_slices,
                    fallback_warning=fallback_warning,
                )
                duplicate_result["_progress"] = False
                return self._remember(
                    action_name,
                    action,
                    duplicate_result,
                    update_last_observation=False,
                )
            if fallback_warning:
                selected_slice["content"] = (
                    fallback_warning + "\n\n" + selected_slice.get("content", "")
                )
            selected_slice["_progress"] = False
            return self._remember(action_name, action, selected_slice)

        if action_name == "get_file_outline":
            file_entry = self._get_file(action["file_path"])
            result = dict(file_entry.get("outline", {}))
            result["_progress"] = False
            return self._remember(action_name, action, result)

        if action_name == "query_librarian":
            question_signature = (
                action.get("question_id"),
                action.get("question", "").strip(),
            )
            is_new_question = not any(
                (
                    entry.get("question_id"),
                    entry.get("question", "").strip(),
                )
                == question_signature
                for entry in self.state.librarian_history
            )
            result = self.librarian.ask(action["question"])
            self.state.librarian_history.append(
                {
                    "question_id": action.get("question_id"),
                    "question": action.get("question"),
                    "answer": _trim_text(result.get("content", ""), 260),
                    "citations": result.get("citations", []),
                    "coverage_note": result.get("coverage_note"),
                }
            )
            result["_progress"] = is_new_question
            return self._remember(action_name, action, result)

        if action_name == "record_evidence":
            if not self.state.last_observation:
                raise ValueError("record_evidence requires a prior observation.")
            observation = self.state.last_observation
            item = EvidenceItem(
                question_id=action["question_id"],
                source_type=observation.get("source_type"),
                commit_sha=self.state.commit_id,
                file_path=observation.get("file_path"),
                line_hint=observation.get("line_hint"),
                slice_id=observation.get("slice_id"),
                content=observation.get("content", ""),
                note=action.get("note", ""),
                citation=", ".join(observation.get("citations", [])) or None,
            )
            entry = item.to_dict()
            is_new_evidence = entry not in self.state.evidence_ledger[action["question_id"]]
            if is_new_evidence:
                self.state.evidence_ledger[action["question_id"]].append(entry)
            result = {
                "source_type": "evidence_record" if is_new_evidence else "duplicate_evidence_record",
                "file_path": item.file_path,
                "commit_sha": self.state.commit_id,
                "line_hint": item.line_hint,
                "slice_id": item.slice_id,
                "content": (
                    f"Recorded evidence for {action['question_id']}: {item.note or 'no extra note'}"
                    if is_new_evidence
                    else f"Evidence for {action['question_id']} was already recorded."
                ),
                "_progress": is_new_evidence,
            }
            return self._remember(action_name, action, result, update_last_observation=False)

        raise ValueError(f"Unsupported tool action: {action_name}")


def render_analysis_markdown(decision):
    lines = [
        f"**Title**: {decision.get('title', '')}",
        f"**Issue**: {decision.get('issue', '')}",
        f"**Tag**: {decision.get('tag', '')}",
        f"**Purpose**: {decision.get('purpose', '')}",
        "---",
        "",
        "### Step-by-Step Analysis:",
        f"1. **Key Variables/Functionality**: {decision.get('step_analysis', {}).get('key_variables_functionality', '')}",
        f"2. **Compiler Behavior**: {decision.get('step_analysis', {}).get('compiler_behavior', '')}",
        f"3. **Pre/Post Compilation**: {decision.get('step_analysis', {}).get('pre_post_compilation', '')}",
        f"4. **Security Implications**: {decision.get('step_analysis', {}).get('security_implications', '')}",
        "---",
        "",
    ]

    for idx, question_id in enumerate(QUESTION_TEXT, start=1):
        answer_entry = decision.get("binary_answers", {}).get(question_id, {})
        answer = answer_entry.get("answer", "unknown")
        reason = answer_entry.get("reason", "")
        lines.append(f"{idx}. [{answer}] {QUESTION_TEXT[question_id]} {reason}".strip())

    lines.append("")
    lines.append(f"**CISB Status**: {decision.get('cisb_status', 'no')}")
    return "\n".join(lines).strip() + "\n"


def render_spec_markdown(decision):
    spec = decision.get("spec", {}) or {}
    lines = [
        f"# Draft Spec for {decision.get('title', 'kernel commit')}",
        "",
        f"- Trigger condition: {spec.get('trigger_condition', '')}",
        f"- Broken security property: {spec.get('broken_security_property', '')}",
        f"- Compiler behavior: {spec.get('compiler_behavior', '')}",
        f"- Affected code pattern: {spec.get('affected_code_pattern', '')}",
        "- Evidence:",
    ]
    for item in spec.get("evidence", []):
        lines.append(f"  - {item}")
    return "\n".join(lines).strip() + "\n"


class AgenticKernelOrchestrator:
    def __init__(
        self,
        dmodel,
        rmodel,
        api_key1,
        api_key2,
        url1,
        url2,
        output_dir=None,
        cache_dir=None,
        cache_policy=None,
        scheduler=None,
        retriever=None,
        digestor_agent=None,
        librarian_agent=None,
        reasoner_agent=None,
        judge_agent=None,
        max_steps=12,
        total_action_limit=40,
    ):
        self.helper = Helper()
        self.output_dir = output_dir or os.getcwd()
        self.cache_dir = str((PROJECT_ROOT / (cache_dir or DEFAULT_CACHE_DIR)).resolve())
        self.cache_policy = cache_policy or {}
        self.scheduler = scheduler if scheduler is not None else KernelApiScheduler()
        self.retriever = retriever if retriever is not None else self._build_retriever()
        self.digestor = digestor_agent or DigestorAgent(dmodel, api_key1, url1)
        self.librarian = librarian_agent or LibrarianAgent(dmodel, api_key1, url1, retriever=self.retriever)
        self.reasoner = reasoner_agent or ReasonerAgent(rmodel, api_key2, url2)
        self.judge = judge_agent or JudgeAgent(rmodel, api_key2, url2)
        self.max_steps = max_steps
        self.total_action_limit = total_action_limit

    def _build_retriever(self):
        try:
            from rag.embedder import Embedder
            from rag.reranker import Reranker
            from rag.retriever import Retriever
        except Exception:
            return None

        api_key = os.getenv("RAG_API_KEY", "")
        base_url = os.getenv("EMBEDDING_API_URL", "")
        model_name = os.getenv("EMBEDDING_MODEL_NAME", "")
        if not (api_key and base_url and model_name):
            return None

        try:
            embedder = Embedder(
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
            )
            reranker = None
            rerank_url = os.getenv("RERANK_API_URL") or os.getenv("RERANKING_API_URL", "")
            rerank_model = os.getenv("RERANK_MODEL_NAME") or os.getenv("RERANKING_MODEL_NAME", "")
            if api_key and rerank_url and rerank_model:
                reranker = Reranker(
                    api_key=api_key,
                    base_url=rerank_url,
                    model_name=rerank_model,
                )
            retriever = Retriever(
                embedder=embedder,
                reranker=reranker,
                knowledge_base_path=str(PROJECT_ROOT / "rag" / "knowledge_base"),
            )
            retriever.ingest_knowledge_base()
            return retriever
        except Exception:
            return None

    def _prepare_state(self, commit_id, seed_report):
        cache = prepare_commit_cache(
            commit_id,
            policy=self.cache_policy,
            cache_dir=self.cache_dir,
            seed_data=seed_report,
            scheduler=self.scheduler,
        )
        return KernelRunState(
            commit_id=commit_id,
            raw_report=seed_report or {},
            cache=cache,
            cache_path=os.path.join(self.cache_dir, f"{commit_id}.json"),
            output_dir=self.output_dir,
            max_steps=self.max_steps,
            total_action_limit=self.total_action_limit,
        )

    def _run_reasoner_loop(self, state):
        tools = KernelToolRegistry(state, self.librarian)
        invalid_actions = 0

        while state.action_count < state.total_action_limit:
            step = state.action_count + 1
            try:
                action = self.reasoner.next_action(state)
            except Exception as exc:
                invalid_actions += 1
                state.errors.append(str(exc))
                state.reasoning_history.append({"step": step, "error": str(exc)})
                if invalid_actions >= state.max_invalid_actions:
                    state.termination_reason = "invalid_action_limit"
                    break
                state.stall_count += 1
                if state.stall_count >= state.max_steps:
                    state.termination_reason = "stall_limit"
                    break
                continue

            state.reasoning_history.append({"step": step, "action": action})
            state.action_count += 1

            if action["action"] == "submit_to_judge":
                state.termination_reason = action.get("summary", "submit_to_judge")
                break

            if action["action"] == "answer_question":
                previous_answer = state.question_answers.get(action["question_id"])
                state.question_answers[action["question_id"]] = {
                    "answer": normalize_answer(action["answer"]),
                    "reason": action["reason"],
                }
                progress = state.question_answers[action["question_id"]] != previous_answer
                if progress:
                    state.stall_count = 0
                else:
                    state.stall_count += 1
                    if state.stall_count >= state.max_steps:
                        state.termination_reason = "stall_limit"
                        break
                continue

            try:
                result = tools.execute(action)
                progress = bool(result.get("_progress"))
                if progress:
                    state.stall_count = 0
                else:
                    state.stall_count += 1
                    if state.stall_count >= state.max_steps:
                        state.termination_reason = "stall_limit"
                        break
            except Exception as exc:
                state.errors.append(f"Tool error: {exc}")
                state.reasoning_history.append(
                    {"step": step, "tool_error": str(exc), "action": action}
                )
                state.stall_count += 1
                if state.stall_count >= state.max_steps:
                    state.termination_reason = "stall_limit"
                    break

        if not state.termination_reason:
            state.termination_reason = "total_action_limit"

    def persist(self, state):
        stem = self.helper.normalize_report_id(state.commit_id)
        analysis_path = os.path.join(state.output_dir, f"{stem}_analysis.md")
        trace_path = os.path.join(state.output_dir, f"{stem}_trace.json")
        spec_path = os.path.join(state.output_dir, f"{stem}_spec.md")

        self.helper.write_text(analysis_path, state.final_decision["analysis_markdown"])
        self.helper.write_json(trace_path, state.to_trace())
        if state.final_decision.get("cisb_status") == "yes":
            self.helper.write_text(spec_path, state.final_decision["spec_markdown"])

    def run(self, commit_id, seed_report=None, persist=True):
        state = self._prepare_state(commit_id, seed_report)
        state.digest = self.digestor.run(state)
        digest_summaries = state.digest.get("function_contexts") or []
        if digest_summaries:
            first_summary = digest_summaries[0]
            state.last_observation = {
                "tool": "digest_context",
                "source_type": "digest_context",
                "file_path": first_summary.get("file_path"),
                "line_hint": "digest",
                "slice_id": first_summary.get("primary_symbol") or "digest_context",
                "content": first_summary.get("code_summary", ""),
            }
        self._run_reasoner_loop(state)
        decision = self.judge.run(state)
        decision["analysis_markdown"] = render_analysis_markdown(decision)
        decision["spec_markdown"] = render_spec_markdown(decision)
        state.final_decision = decision
        if persist:
            self.persist(state)
        return state
