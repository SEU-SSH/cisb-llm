"""
Run commits through Digestor -> Reasoner(with RAG).

Default behavior:
- Output analysis files only (no RAG trace files).
- Support rerun subset commits from commits.txt.

Usage examples:
    python run_single_commit_rag_trace.py --json P_commits.json --commits-file commits.txt
    python run_single_commit_rag_trace.py --json P_commits.json --commit-id <commit_hash>
    python run_single_commit_rag_trace.py --json P_commits.json --commits-file commits.txt --trace
"""

import os
import json
import argparse
import sys
import time
from datetime import datetime

import dotenv
from openai import OpenAI

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR = os.path.join(PROJECT_ROOT, "agents")
RAG_DIR = os.path.join(PROJECT_ROOT, "rag")

# agents/ modules rely on bare imports (e.g. "from agent import Agent").
sys.path.insert(0, AGENTS_DIR)
sys.path.insert(0, RAG_DIR)

from agents.digestor import Digestor
from agents.helper import Helper
from rag.embedder import Embedder
from rag.reranker import Reranker
from rag.retriever import Retriever


KERNEL_DIGESTOR_PROMPT = """You are an expert git commit info extraction assistant. Your task is to analyze the given commit and extract key information in JSON format.
\nThe report will contain bug id, year, message and patch context, wholly formed as a json.
\nRephrase developer description in message as a standardized expression in the computer science field. If the message contains source code, extract and append in the [patch context] naming 'message code'.
\nFirst focus on the provided source code in patches, try to divide it into some logical blocks, summarize their patched code per file.
\nThen, associate the code with developer description, conclude the previous issue, patching purpose and compiler behavior from it according to the output.
\nOutput should include following information, constructed as a json: \n{
[id]: The bug id of the report.
[title]: The first sentence of the message, stored as-is.
[previous issue]:
[patching purpose]:
[compiler behavior]:
[patch context]: extracted from patch context and message, stored per file, as-is.
[message code]: code extracted from message, if any.
[code block1]: {[before]}
[code block2]: {[before]}
...\n}"""


KERNEL_PROMPT_RAG_TEMPLATE = """You are an expert in the field of software and system security.
\nYour task is to analyse a commit from Linux kernel, determine whether the patch reveals a potential [CISB].
\n\n[Bug Report Structure]: The report contains commit id, title, digested description, patch context and diff code logical blocks, formed as json.
\n[Requirement 1]: Do not overthink or recommend anything.
\n[Requirement 2]: Your reason must base on source code. If lacking enough source code, terminate the inference directly and raise exception.
\n[Requirement 3]: Do not care if compiler contains a bug, but if the CISB exists in the code. Do not blame nor make value judgment.
\n[Requirement 4]: You MUST use the [Retrieved Knowledge] section below as your reference for concept definitions, distinctions, and decision criteria. Apply the retrieved knowledge accurately during your reasoning. Do not fabricate definitions or criteria beyond what is provided.
\n\n[Retrieved Knowledge]
{rag_context}
\n\nLet us reason about it step by step.
\n[Step 1]: Locate key variables or function calls in the code blocks, trace them through call chains in the patch context. Then summarize their functionality. If you cannot locate a specific source code, terminate early and report the exception.
\n[Step 2]: According to the issue in message, analyse the probable optimization or default behavior done by compiler on the located code block. Do not rush to a conclusion.
\n[Step 3]: Contrast the previous functionality and the actual after compilation, whether it differs after the compiler process in Step 2. It is not about patch difference but compilation process.
\n[Step 4]: Judge if the issue is caused by the differences in Step 3, and whether may have security implications in kernel context. No matter what the root cause is.
\n\nAfter reasoning, you should conclude your reasoning content, then output the analysis results in below structure.
\n\n**Title**: brief conclusion of the commit.
\n**Issue**: how the program observable behavior differs from expectation.
\n**Tag**: classify the commit within a phrase. Such as code enhance, config fix, etc.
\n**Purpose**: what the commit intend to edit or revise.
\n---\n
### Step-by-Step Analysis:
\n1. **Key Variables/Functionality**: where the issue emerges on source code.
\n2. **Compiler Behavior**: whether and what the optimization, default behavior on specific code.
\n3. **Pre/Post Compilation**: the difference before and after compiler process on code, not patch diff.
\n4. **Security Implications**: whether the difference damages security in kernel context.
\n---\n
\nAnswer the following questions with [yes/no] and one sentence explanation:
\n1. Did compiler accept the kernel code and compile it successfully?
\n2. Is the issuer reporting a runtime bug, where previous code semantic assumption was damaged during optimization or default behavior?
\n3. Without optimization or default behavior, will the difference in Step 3 disappear?
\n4. Did the program observable behavior change after optimization or default behavior during execution?
\n5. Does this change have direct or indirect security implications in the context?
\n\n**CISB Status**: If answers are all [yes], then it is a CISB."""


def load_env():
    dotenv.load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    return {
        "DS_API_KEY": os.getenv("DS_API_KEY", ""),
        "DS_API_URL": os.getenv("DS_API_URL", ""),
        "DS_MODEL_NAME": os.getenv("DS_MODEL_NAME", ""),
        "QWEN_API_KEY": os.getenv("QWEN_API_KEY", ""),
        "QWEN_API_URL": os.getenv("QWEN_API_URL", ""),
        "QWEN_MODEL_NAME": os.getenv("QWEN_MODEL_NAME", ""),
        "RAG_API_KEY": os.getenv("RAG_API_KEY", ""),
        "EMBEDDING_API_URL": os.getenv("EMBEDDING_API_URL", ""),
        "EMBEDDING_MODEL_NAME": os.getenv("EMBEDDING_MODEL_NAME", ""),
        "RERANKING_API_URL": os.getenv("RERANK_API_URL")
        or os.getenv("RERANKING_API_URL", ""),
        "RERANKING_MODEL_NAME": os.getenv("RERANK_MODEL_NAME")
        or os.getenv("RERANKING_MODEL_NAME", ""),
    }


def load_commit_dataset(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_commit(commits, commit_id=None):
    if commit_id:
        if commit_id not in commits:
            raise KeyError(f"Commit id not found in dataset: {commit_id}")
        return commit_id, commits[commit_id]

    first_id = next(iter(commits.keys()))
    return first_id, commits[first_id]


def read_commit_ids(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def pick_commits_by_ids(commits, commit_ids):
    selected = []
    missing = []
    for commit_id in commit_ids:
        if commit_id in commits:
            selected.append((commit_id, commits[commit_id]))
        else:
            missing.append(commit_id)
    return selected, missing


def build_digestor(env):
    return Digestor(
        model=env["DS_MODEL_NAME"],
        prompt=KERNEL_DIGESTOR_PROMPT,
        API_KEY=env["DS_API_KEY"],
        URL=env["DS_API_URL"],
        platform="kernel",
    )


def build_retriever(env):
    embedder = Embedder(
        api_key=env["RAG_API_KEY"],
        base_url=env["EMBEDDING_API_URL"],
        model_name=env["EMBEDDING_MODEL_NAME"],
    )
    reranker = None
    if (
        env["RAG_API_KEY"]
        and env["RERANKING_API_URL"]
        and env["RERANKING_MODEL_NAME"]
    ):
        reranker = Reranker(
            api_key=env["RAG_API_KEY"],
            base_url=env["RERANKING_API_URL"],
            model_name=env["RERANKING_MODEL_NAME"],
        )

    retriever = Retriever(
        embedder=embedder,
        reranker=reranker,
        knowledge_base_path=os.path.join(PROJECT_ROOT, "rag", "knowledge_base"),
    )
    doc_count = retriever.ingest_knowledge_base()
    return retriever, doc_count


def run_digest(digestor, commit_data):
    response = digestor.chat(commit_data)
    return Helper().extract_response_json(response)


def build_rag_query_from_digest(digest):
    query_parts = []
    for key in ("previous issue", "compiler behavior", "patching purpose"):
        value = digest.get(key)
        if value:
            query_parts.append(str(value))

    if query_parts:
        return " ".join(query_parts)

    return json.dumps(digest, ensure_ascii=False)[:1000]


def format_retrieved_context(entries):
    if not entries:
        return ""
    context_parts = []
    for entry in entries:
        source = entry.get("source")
        header = entry.get("header")
        content = entry.get("content", "")
        context_parts.append(f"[Source: {source} > {header}]\n{content}")
    return "\n\n---\n\n".join(context_parts)


def run_reason_with_rag(
    env,
    digest,
    retriever,
    top_k=3,
    use_stream=False,
    collect_trace=False,
):
    query = build_rag_query_from_digest(digest)

    retrieved_entries = None
    if collect_trace:
        retrieved_entries = retriever.retrieve(query, top_k=top_k)
        rag_context = format_retrieved_context(retrieved_entries)
    else:
        rag_context = retriever.retrieve_as_context(query, top_k=top_k)

    if not rag_context:
        rag_context = "(No relevant knowledge retrieved.)"

    system_prompt = KERNEL_PROMPT_RAG_TEMPLATE.format(rag_context=rag_context)

    client = OpenAI(api_key=env["QWEN_API_KEY"], base_url=env["QWEN_API_URL"])
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(digest, ensure_ascii=False)},
    ]
    response = client.responses.create(
        model=env["QWEN_MODEL_NAME"],
        input=messages,
        extra_body={"enable_thinking": True} if use_stream else None,
        temperature=1.0,
        stream=use_stream,
    )

    if use_stream:
        answer_content = ""
        for chunk in response:
            chunk_type = chunk.get("type") if isinstance(chunk, dict) else getattr(chunk, "type", None)
            if chunk_type == "response.output_text.delta":
                delta = chunk.get("delta", "") if isinstance(chunk, dict) else getattr(chunk, "delta", "")
                answer_content += delta
        analysis_text = answer_content
    else:
        analysis_text = Helper().extract_response_text(response)

    return {
        "query": query,
        "retrieved_entries": retrieved_entries,
        "rag_context": rag_context,
        "system_prompt": system_prompt,
        "analysis_text": analysis_text,
    }


def write_outputs(output_dir, commit_id, source_json, commit_data, digest, trace):
    os.makedirs(output_dir, exist_ok=True)
    short_id = commit_id[:10] if len(commit_id) > 10 else commit_id

    trace_path = os.path.join(output_dir, f"{short_id}_rag_trace.json")
    analysis_path = os.path.join(output_dir, f"{short_id}_analysis.md")

    trace_payload = {
        "timestamp": datetime.now().isoformat(),
        "source_json": source_json,
        "commit_id": commit_id,
        "commit": commit_data,
        "digest": digest,
        "reason_with_rag_query": trace["query"],
        "retrieved_entries": trace["retrieved_entries"],
        "rag_context": trace["rag_context"],
        "system_prompt_with_rag": trace["system_prompt"],
        "analysis": trace["analysis_text"],
    }

    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_payload, f, indent=2, ensure_ascii=False)

    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write("[Generated summary]\n")
        f.write(trace["analysis_text"])

    return trace_path, analysis_path


def write_analysis_only(output_dir, commit_id, analysis_text):
    os.makedirs(output_dir, exist_ok=True)
    short_id = commit_id[:10] if len(commit_id) > 10 else commit_id
    analysis_path = os.path.join(output_dir, f"{short_id}_analysis.md")
    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write("[Generated summary]\n")
        f.write(analysis_text)
    return analysis_path


def main():
    parser = argparse.ArgumentParser(
        description="Run commits through Digestor -> Reasoner(with RAG).",
    )
    parser.add_argument(
        "--json",
        default="P_commits.json",
        help="Path to commit source json file. Default: P_commits.json",
    )
    parser.add_argument(
        "--commit-id",
        default=None,
        help="Specific commit id in the json.",
    )
    parser.add_argument(
        "--commits-file",
        default=None,
        help="Path to txt file containing commit ids (one per line).",
    )
    parser.add_argument(
        "--output-dir",
        default="results/rag_rerun",
        help="Output directory for analysis (and trace when enabled).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Retriever top-k. Default: 5",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Sleep seconds between commits. Default: 30",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Enable RAG trace output json (query/retrieval/system_prompt).",
    )
    args = parser.parse_args()

    source_json = args.json
    if not os.path.isabs(source_json):
        source_json = os.path.join(PROJECT_ROOT, source_json)

    output_dir = args.output_dir
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(PROJECT_ROOT, output_dir)

    env = load_env()

    commits = load_commit_dataset(source_json)
    print(f"[Input] commit source: {source_json}")

    if args.commit_id and args.commits_file:
        raise ValueError("Use either --commit-id or --commits-file, not both.")

    if args.commits_file:
        commits_file_path = args.commits_file
        if not os.path.isabs(commits_file_path):
            commits_file_path = os.path.join(PROJECT_ROOT, commits_file_path)
        commit_ids = read_commit_ids(commits_file_path)
        selected_commits, missing_ids = pick_commits_by_ids(commits, commit_ids)
        print(f"[Input] commits file: {commits_file_path}")
        print(f"[Input] selected: {len(selected_commits)} commit(s)")
        if missing_ids:
            print(f"[Warn] missing in source json: {len(missing_ids)}")
            for missing_id in missing_ids:
                print(f"  - {missing_id}")
    elif args.commit_id:
        commit_id, commit_data = pick_commit(commits, args.commit_id)
        selected_commits = [(commit_id, commit_data)]
        print(f"[Input] selected commit: {commit_id[:10]}")
    else:
        commit_id, commit_data = pick_commit(commits, None)
        selected_commits = [(commit_id, commit_data)]
        print(f"[Input] selected commit: {commit_id[:10]}")

    digestor = build_digestor(env)
    retriever, doc_count = build_retriever(env)
    print(f"[RAG] indexed sections: {doc_count}")
    print(f"[Mode] trace enabled: {args.trace}")

    failures = []
    total = len(selected_commits)

    for index, (commit_id, commit_data) in enumerate(selected_commits, start=1):
        short_id = commit_id[:10] if len(commit_id) > 10 else commit_id
        print(f"\n[{index}/{total}] {short_id}")

        try:
            print("[Step] digesting commit...")
            digest = run_digest(digestor, commit_data)

            print("[Step] reasoning with RAG...")
            trace = run_reason_with_rag(
                env=env,
                digest=digest,
                retriever=retriever,
                top_k=args.top_k,
                use_stream=False,
                collect_trace=args.trace,
            )

            if args.trace:
                trace_path, analysis_path = write_outputs(
                    output_dir=output_dir,
                    commit_id=commit_id,
                    source_json=source_json,
                    commit_data=commit_data,
                    digest=digest,
                    trace=trace,
                )
                print(f"[Saved] trace: {trace_path}")
                print(f"[Saved] analysis: {analysis_path}")
            else:
                analysis_path = write_analysis_only(
                    output_dir=output_dir,
                    commit_id=commit_id,
                    analysis_text=trace["analysis_text"],
                )
                print(f"[Saved] analysis: {analysis_path}")

        except Exception as e:
            failures.append((commit_id, str(e)))
            print(f"[Error] {short_id}: {e}")

        if index < total and args.interval > 0:
            print(f"[Sleep] {args.interval}s")
            time.sleep(args.interval)

    print("\n[Done] Pipeline finished.")
    print(f"[Summary] success: {total - len(failures)}/{total}")
    if failures:
        print(f"[Summary] failures: {len(failures)}")
        for commit_id, error in failures:
            print(f"  - {commit_id[:10]}: {error}")


if __name__ == "__main__":
    main()
