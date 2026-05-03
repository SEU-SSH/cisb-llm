# CISB Specification

## Vulnerability Description

**Source**
Linux kernel commit 9bc4f28af75a91aea0ae383f50b0a430c4509303 (2018), x86/mm subsystem

**Description**
Compiler may optimize assignments to page table entries (PTEs, PMDs, PUDs, PGDs) into multiple store instructions without WRITE_ONCE(). This creates an interim non-present PTE state that could be exploited via L1TF vulnerability. Developer expects atomic single-write behavior for memory-mapped hardware structures controlling memory access permissions.

**Evidence**
Compiler optimization splits single assignment statement into multiple store instructions. Binary differences observed between patched and unpatched versions (greater when CONFIG_PARAVIRT=n). WRITE_ONCE() forces single store instruction or equivalent atomic sequence, eliminating transient vulnerable state.

**Requirement**
x86 architecture, Linux kernel context, compiler optimization enabled (default behavior), page table entry modification code paths

**Mitigation**
Use WRITE_ONCE() macro for all page table entry assignments. Alternative: use atomic operations or memory barriers. Compiler option -fno-builtin may help but WRITE_ONCE() is the proper kernel mechanism.

---

## Code Pattern

```json
{
  "triggers": [
    "Compiler optimization splits single assignment into multiple store instructions",
    "Memory-mapped hardware structure requires atomic write semantics",
    "No explicit volatile or atomic annotation on the assignment"
  ],
  "vulnerable_pattern": "Plain assignment to dereferenced pointer targeting memory-mapped hardware structure (e.g., page table entries) without WRITE_ONCE() or equivalent atomic annotation. Pattern: *ptr = value where ptr points to hardware-controlled memory that requires atomic update semantics. The assignment may be compiled into multiple store instructions, creating intermediate states observable by other agents (hardware, other CPUs, or speculative execution).",
  "ql_constraints": "Match assignment expressions where: (1) left-hand side is a dereference operation (pointer dereference, array access, or field access through pointer), (2) the target object is memory-mapped hardware structure or shared memory requiring atomic semantics, (3) no WRITE_ONCE(), READ_ONCE(), atomic operations, or volatile qualification present on the assignment, (4) data flow links the assigned value source to the dereference target within same function or through argument-passing chain. Do not require specific variable names, type names, or macro names. Link by same memory object rather than exact AST occurrence.",
  "equivalence_notes": [
    "*ptr = value, ptr->field = value, ((T*)ptr)->field = value are semantically equivalent dereference patterns",
    "Declaration initialization (T x = expr) and later assignment (x = expr) are equivalent value sources",
    "Array access arr[i] = value and pointer access *(arr + i) = value are equivalent after array decay",
    "Whole-object initialization, zero initialization, or aggregate copy may be lowered into memcpy/memset - treat as same semantic family"
  ],
  "scope_assumptions": [
    "Within the same function for direct assignment patterns",
    "Cross-function relation through the same argument object when pointer is passed to callee"
  ],
  "control_flow_assumptions": [
    "No specific control flow required - vulnerability exists regardless of branch/loop structure",
    "The write operation itself is the vulnerability point, not its position relative to branches"
  ],
  "environment_assumptions": [
    "Compiler optimization enabled (default behavior may split writes)",
    "x86 architecture with page table manipulation",
    "Kernel context where page table entries control memory access permissions",
    "Hardware vulnerability (L1TF or similar) can exploit transient non-present PTE states"
  ]
}
```

---

## Provenance

- Source analysis: /home/suiren/cisb-llm/results/kernel/P/9bc4f28af7_analysis.md
- Source id: 9bc4f28af7
- Digest: available
- Generated at: 2026-05-01T13:51:40.272067+00:00
- Model: qwen3.5-397b-a17b
