"""
Contrast Experiment: NoRAG vs MinimalRAG for CISB Detection on Kernel Commits.

Workflow:
  1. Run positive samples (P_commits.json):
     a) NoRAG mode  → results/NoRAG/P/
     b) Sleep 30 min
     c) MinimalRAG mode → results/MinimalRAG/P/
  2. Run negative samples (N_commits.json):
     a) NoRAG mode  → results/NoRAG/N/
     b) Sleep 30 min
     c) MinimalRAG mode → results/MinimalRAG/N/

Usage:
    python contrast_experiment.py               # run full experiment
    python contrast_experiment.py --phase P     # run positive samples only
    python contrast_experiment.py --phase N     # run negative samples only
    python contrast_experiment.py --mode norag  # run NoRAG only (both P and N)
    python contrast_experiment.py --mode rag    # run MinimalRAG only (both P and N)
    python contrast_experiment.py --sleep 0     # skip sleep (for debugging)
"""

import sys
import os
import json
import time
import argparse
import traceback

import dotenv

# ---------------------------------------------------------------------------
# Path setup: ensure agents/ and rag/ modules are importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR = os.path.join(PROJECT_ROOT, "agents")
RAG_DIR = os.path.join(PROJECT_ROOT, "rag")

sys.path.insert(0, AGENTS_DIR)
sys.path.insert(0, RAG_DIR)

from openai import OpenAI
from agents.digestor import Digestor
from agents.helper import Helper
from rag.embedder import Embedder
from rag.reranker import Reranker
from rag.retriever import Retriever

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------
dotenv.load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

DS_API_KEY = os.getenv("DS_API_KEY", "")
DS_API_URL = os.getenv("DS_API_URL", "")
DS_MODEL_NAME = os.getenv("DS_MODEL_NAME", "")

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_API_URL = os.getenv("QWEN_API_URL", "")
QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "")

RAG_API_KEY = os.getenv("RAG_API_KEY", "")
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "")
RERANKING_API_URL = os.getenv("RERANK_API_URL") or os.getenv("RERANKING_API_URL", "")
RERANKING_MODEL_NAME = os.getenv("RERANK_MODEL_NAME") or os.getenv(
    "RERANKING_MODEL_NAME", ""
)

# ---------------------------------------------------------------------------
# Data paths
# ---------------------------------------------------------------------------
P_COMMITS_PATH = os.path.join(PROJECT_ROOT, "P_commits.json")
N_COMMITS_PATH = os.path.join(PROJECT_ROOT, "N_commits.json")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

# ---------------------------------------------------------------------------
# Default sleep duration between NoRAG and MinimalRAG (seconds)
# ---------------------------------------------------------------------------
DEFAULT_SLEEP_SECONDS = 30 * 60  # 30 minutes
REQUEST_INTERVAL = 30  # seconds between individual LLM requests

# ---------------------------------------------------------------------------
# Prompt: Original Kernel Reasoner (NoRAG) — unchanged from reasoner.py
# ---------------------------------------------------------------------------
KERNEL_PROMPT_NORAG = """You are an expert in the field of software and system security.
\nYour task is to analyse a commit from Linux kernel, determine whether the patch reveals a potential [CISB].
\n\n[Bug Report Structure]: The report contains commit id, title, digested description, patch context and diff code logical blocks, formed as json.
\n[Requirement 1]: Do not overthink or recommend anything.
\n[Requirement 2]: Your reason must base on source code. If lacking enough source code, terminate the inference directly and raise exception.
\n[Requirement 3]: Do not care if compiler contains a bug, but if the CISB exists in the code. Do not blame nor make value judgment.
\n[Requirement 4]: Concepts you MUST distinguish: \n<Default Behavior>: compilers decide it is appropriate to perform certain default behaviors or make default assumptions. Such as inlining, type promotion, assuming function must return, etc.\n<Programming Error>: Violations explicitly marked as invalid by the language specification (e.g., constraint violations, reserved keyword misuse). \n<Undefined Behavior> (UB): Behavior where the standard imposes no requirements. UB is not necessarily programming error because in sometimes it is required in certain environment, such as data race in kernel. Do not assume that all UB cases indicate programming error.
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
\nDirect implications such as endless loop/program hang, crash, memory corruption, etc. Indirect implications such as data leak, control flow diversion, check removed/bypassed, and more covert like side channel, speculative execution, etc.
\n\n**CISB Status**: If answers are all [yes], then it is a CISB."""

# MinimalRAG Kernel Reasoner prompt
# vs NoRAG: [Requirement 4] replaced with RAG retrieval instruction;
#           Q5 security examples removed (provided via knowledge base instead)
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

# ---------------------------------------------------------------------------
# Kernel Digestor prompt (unchanged)
# ---------------------------------------------------------------------------
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


# ===========================================================================
# Core functions
# ===========================================================================


def load_commits(filepath):
    """Load commit dataset and return dict of commit_hash -> commit_obj."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dirs():
    """Create results directory structure."""
    for mode in ("NoRAG", "MinimalRAG"):
        for sample_type in ("P", "N"):
            path = os.path.join(RESULTS_DIR, mode, sample_type)
            os.makedirs(path, exist_ok=True)
    print(f"[Setup] Results directory structure ready: {RESULTS_DIR}/")


def build_digestor():
    """Build a Digestor instance with Kernel platform settings."""
    digestor = Digestor(
        model=DS_MODEL_NAME,
        prompt=KERNEL_DIGESTOR_PROMPT,
        API_KEY=DS_API_KEY,
        URL=DS_API_URL,
        platform="kernel",
    )
    digestor.prompt = KERNEL_DIGESTOR_PROMPT
    return digestor


def build_retriever():
    """Build and initialize the RAG Retriever."""
    embedder = Embedder(
        api_key=RAG_API_KEY,
        base_url=EMBEDDING_API_URL,
        model_name=EMBEDDING_MODEL_NAME,
    )
    reranker = None
    if RAG_API_KEY and RERANKING_API_URL and RERANKING_MODEL_NAME:
        reranker = Reranker(
            api_key=RAG_API_KEY,
            base_url=RERANKING_API_URL,
            model_name=RERANKING_MODEL_NAME,
        )
    retriever = Retriever(
        embedder=embedder,
        reranker=reranker,
        knowledge_base_path=os.path.join(RAG_DIR, "knowledge_base"),
    )
    print("[RAG] Ingesting knowledge base...")
    num_docs = retriever.ingest_knowledge_base()
    print(f"[RAG] Indexed {num_docs} document sections.")
    return retriever


def digest_commit(digestor, commit_data):
    """Run Digestor on a commit and return the parsed digest dict."""
    client = OpenAI(api_key=digestor.API_KEY, base_url=digestor.URL)
    response = client.chat.completions.create(
        model=digestor.model,
        messages=[
            {"role": "system", "content": digestor.prompt},
            {"role": "user", "content": str(commit_data)},
        ],
        max_tokens=4096,
        temperature=1.0,
        response_format={"type": "json_object"},
        stream=False,
    )
    digest_text = response.choices[0].message.content
    return json.loads(digest_text)


def reason_norag(reasoner_model, reasoner_api_key, reasoner_url, digest, use_stream):
    """Run Reasoner in NoRAG mode. Returns the response object."""
    client = OpenAI(api_key=reasoner_api_key, base_url=reasoner_url)
    messages = [
        {"role": "system", "content": KERNEL_PROMPT_NORAG},
        {"role": "user", "content": json.dumps(digest, ensure_ascii=False)},
    ]
    if use_stream:
        response = client.responses.create(
            model=reasoner_model,
            input=messages,
            extra_body={"enable_thinking": True},
            temperature=1.0,
            stream=True,
        )
    else:
        response = client.responses.create(
            model=reasoner_model,
            input=messages,
            temperature=1.0,
            stream=False,
        )
    return response


def reason_with_rag(
    reasoner_model, reasoner_api_key, reasoner_url, digest, retriever, use_stream
):
    """Run Reasoner in MinimalRAG mode. Retrieves context and injects into prompt."""
    query_parts = []
    for key in ("previous issue", "compiler behavior", "patching purpose"):
        val = digest.get(key)
        if val:
            query_parts.append(str(val))
    query = (
        " ".join(query_parts)
        if query_parts
        else json.dumps(digest, ensure_ascii=False)[:1000]
    )

    rag_context = retriever.retrieve_as_context(query, top_k=5)
    if not rag_context:
        rag_context = "(No relevant knowledge retrieved.)"

    system_prompt = KERNEL_PROMPT_RAG_TEMPLATE.format(rag_context=rag_context)

    client = OpenAI(api_key=reasoner_api_key, base_url=reasoner_url)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(digest, ensure_ascii=False)},
    ]
    if use_stream:
        response = client.responses.create(
            model=reasoner_model,
            input=messages,
            extra_body={"enable_thinking": True},
            temperature=1.0,
            stream=True,
        )
    else:
        response = client.responses.create(
            model=reasoner_model,
            input=messages,
            temperature=1.0,
            stream=False,
        )
    return response


def save_analysis(commit_data, response, output_dir, use_stream):
    """Save analysis report to the specified output directory."""
    helper = Helper()
    commit_id = commit_data["id"]
    short_id = commit_id[:10] if len(commit_id) > 10 else commit_id
    filename = os.path.join(output_dir, f"{short_id}_analysis.md")

    if use_stream:
        reasoning_content = ""
        answer_content = ""
        with open(filename, "w", encoding="utf-8") as f:
            for chunk in response:
                chunk_type = (
                    chunk.get("type")
                    if isinstance(chunk, dict)
                    else getattr(chunk, "type", None)
                )
                if chunk_type == "response.output_text.delta":
                    delta = (
                        chunk.get("delta", "")
                        if isinstance(chunk, dict)
                        else getattr(chunk, "delta", "")
                    )
                    answer_content += delta
                    continue
                if hasattr(chunk, "choices") and chunk.choices:
                    delta = getattr(chunk.choices[0], "delta", None)
                    if delta is not None:
                        if (
                            hasattr(delta, "reasoning_content")
                            and delta.reasoning_content
                        ):
                            reasoning_content += delta.reasoning_content
                        if hasattr(delta, "content") and delta.content:
                            answer_content += delta.content

            if not answer_content:
                answer_content = helper.extract_response_text(response)
            f.write("[Reasoning process]\n")
            f.write(reasoning_content)
            f.write("\n\n[Generated summary]\n")
            f.write(answer_content)
    else:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("[Generated summary]\n")
            f.write(helper.extract_response_text(response))

    print(f"  Saved: {filename}")


def run_batch(
    commits,
    digestor,
    mode,
    sample_type,
    output_dir,
    reasoner_model,
    reasoner_api_key,
    reasoner_url,
    use_stream,
    retriever=None,
):
    """Run all commits through Digestor→Reasoner pipeline, saving results to output_dir."""
    total = len(commits)
    errors = []

    print(f"\n{'=' * 60}")
    print(f"[{mode}] Processing {sample_type} samples ({total} commits)")
    print(f"  Output: {output_dir}")
    print(f"  Reasoner: {reasoner_model}")
    print(f"  Stream: {use_stream}")
    print(f"{'=' * 60}\n")

    for idx, (commit_hash, commit_data) in enumerate(commits.items(), 1):
        short_id = commit_hash[:10]
        print(f"[{idx}/{total}] {short_id} — ", end="", flush=True)

        try:
            print("digesting... ", end="", flush=True)
            digest = digest_commit(digestor, commit_data)
            print("reasoning... ", end="", flush=True)

            if mode == "MinimalRAG":
                response = reason_with_rag(
                    reasoner_model,
                    reasoner_api_key,
                    reasoner_url,
                    digest,
                    retriever,
                    use_stream,
                )
            else:
                response = reason_norag(
                    reasoner_model,
                    reasoner_api_key,
                    reasoner_url,
                    digest,
                    use_stream,
                )

            save_analysis(commit_data, response, output_dir, use_stream)

        except Exception as e:
            print(f"ERROR: {e}")
            traceback.print_exc()
            errors.append({"id": commit_hash, "error": str(e)})
            continue

        if idx < total:
            print(f"  (sleeping {REQUEST_INTERVAL}s for rate limit)")
            time.sleep(REQUEST_INTERVAL)

    print(f"\n[{mode}/{sample_type}] Complete: {total - len(errors)}/{total} succeeded")
    if errors:
        print(f"  Errors ({len(errors)}):")
        for err in errors:
            print(f"    {err['id'][:10]}: {err['error']}")

    return errors


# ===========================================================================
# Orchestration
# ===========================================================================


def run_phase(sample_type, commits, args, digestor, retriever):
    """
    Run one phase (P or N) of the experiment:
      1. NoRAG run
      2. Sleep
      3. MinimalRAG run
    """
    reasoner_model = QWEN_MODEL_NAME
    reasoner_api_key = QWEN_API_KEY
    reasoner_url = QWEN_API_URL
    use_stream = reasoner_model != "deepseek-reasoner"

    run_modes = []
    if args.mode in ("all", "norag"):
        run_modes.append("NoRAG")
    if args.mode in ("all", "rag"):
        run_modes.append("MinimalRAG")

    all_errors = {}

    for i, mode in enumerate(run_modes):
        output_dir = os.path.join(RESULTS_DIR, mode, sample_type)

        if mode == "MinimalRAG":
            errors = run_batch(
                commits,
                digestor,
                mode,
                sample_type,
                output_dir,
                reasoner_model,
                reasoner_api_key,
                reasoner_url,
                use_stream,
                retriever=retriever,
            )
        else:
            errors = run_batch(
                commits,
                digestor,
                mode,
                sample_type,
                output_dir,
                reasoner_model,
                reasoner_api_key,
                reasoner_url,
                use_stream,
            )

        all_errors[mode] = errors

        if i < len(run_modes) - 1 and args.sleep_seconds > 0:
            print(f"\n{'=' * 60}")
            print(
                f"[Sleep] Waiting {args.sleep_seconds // 60} minutes before next mode..."
            )
            print(f"{'=' * 60}")
            time.sleep(args.sleep_seconds)

    return all_errors


def main():
    parser = argparse.ArgumentParser(
        description="CISB Detection Contrast Experiment: NoRAG vs MinimalRAG",
    )
    parser.add_argument(
        "--phase",
        choices=["P", "N", "all"],
        default="all",
        help="Which sample phase to run (P=positive, N=negative, all=both). Default: all",
    )
    parser.add_argument(
        "--mode",
        choices=["norag", "rag", "all"],
        default="all",
        help="Which mode to run (norag, rag, all). Default: all",
    )
    parser.add_argument(
        "--sleep",
        dest="sleep_seconds",
        type=int,
        default=DEFAULT_SLEEP_SECONDS,
        help=f"Sleep seconds between NoRAG and MinimalRAG. Default: {DEFAULT_SLEEP_SECONDS} (30 min). Set 0 to skip.",
    )
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Setup
    # -----------------------------------------------------------------------
    print("=" * 60)
    print("CISB Contrast Experiment: NoRAG vs MinimalRAG")
    print("=" * 60)

    ensure_dirs()

    print("\n[Setup] Building Digestor...")
    digestor = build_digestor()
    print(f"  Model: {DS_MODEL_NAME}")

    retriever = None
    if args.mode in ("all", "rag"):
        print("\n[Setup] Building RAG Retriever...")
        retriever = build_retriever()

    print(f"\n[Config]")
    print(f"  Digestor model: {DS_MODEL_NAME}")
    print(f"  Reasoner model: {QWEN_MODEL_NAME}")
    print(f"  Phase: {args.phase}")
    print(f"  Mode: {args.mode}")
    print(
        f"  Sleep between modes: {args.sleep_seconds}s ({args.sleep_seconds // 60} min)"
    )

    confirm = input("\nReady to start? (y/n) ")
    if confirm.lower() != "y":
        print("Aborted.")
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Load data
    # -----------------------------------------------------------------------
    p_commits = load_commits(P_COMMITS_PATH)
    n_commits = load_commits(N_COMMITS_PATH)
    print(f"\n[Data] P_commits: {len(p_commits)} entries")
    print(f"[Data] N_commits: {len(n_commits)} entries")

    # -----------------------------------------------------------------------
    # Execution
    # -----------------------------------------------------------------------
    experiment_errors = {}

    if args.phase in ("all", "P"):
        print(f"\n{'#' * 60}")
        print(f"# PHASE 1: Positive Samples (P)")
        print(f"{'#' * 60}")
        experiment_errors["P"] = run_phase("P", p_commits, args, digestor, retriever)

        if args.phase == "all" and args.sleep_seconds > 0:
            print(f"\n{'=' * 60}")
            print(
                f"[Sleep] Waiting {args.sleep_seconds // 60} minutes before negative samples..."
            )
            print(f"{'=' * 60}")
            time.sleep(args.sleep_seconds)

    if args.phase in ("all", "N"):
        print(f"\n{'#' * 60}")
        print(f"# PHASE 2: Negative Samples (N)")
        print(f"{'#' * 60}")
        experiment_errors["N"] = run_phase("N", n_commits, args, digestor, retriever)

    # -----------------------------------------------------------------------
    # Final summary
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("EXPERIMENT COMPLETE")
    print(f"{'=' * 60}")
    print(f"Results saved to: {RESULTS_DIR}/")
    print(f"  NoRAG/P/      — Positive samples without RAG")
    print(f"  NoRAG/N/      — Negative samples without RAG")
    print(f"  MinimalRAG/P/ — Positive samples with MinimalRAG")
    print(f"  MinimalRAG/N/ — Negative samples with MinimalRAG")

    total_errors = 0
    for phase, mode_errors in experiment_errors.items():
        for mode, errs in mode_errors.items():
            if errs:
                total_errors += len(errs)
                print(f"\n  [{mode}/{phase}] {len(errs)} error(s):")
                for err in errs:
                    print(f"    {err['id'][:10]}: {err['error']}")

    if total_errors == 0:
        print("\nAll runs completed successfully.")
    else:
        print(f"\nTotal errors: {total_errors}")

    error_log_path = os.path.join(RESULTS_DIR, "experiment_errors.json")
    with open(error_log_path, "w", encoding="utf-8") as f:
        json.dump(experiment_errors, f, indent=2, ensure_ascii=False)
    print(f"Error log saved: {error_log_path}")


if __name__ == "__main__":
    main()
