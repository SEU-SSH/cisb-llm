# CISB Specification

## Vulnerability Description

**Source**
Linux Kernel Commit 04ef0f1a01 (IB/mlx4: Fix unaligned access in send_reply_to_slave)

**Description**
Compiler optimizes 8-byte struct copies or memory accesses using aligned load instructions based on default type alignment assumptions. When the actual pointer is only 4-byte aligned, this causes unaligned access faults on strict alignment architectures. The struct definition lacked explicit alignment attributes, leading the compiler to assume natural alignment.

**Evidence**
Compiler emits aligned load instructions (e.g., ldx) for 8-byte data copies. Runtime fault occurs when pointer is only 4-byte aligned on architectures requiring strict alignment. Fix adds __packed __aligned(4) to struct definition to force compiler to generate safe access instructions.

**Requirement**
Compiler optimization enabled. Target architecture enforces strict alignment (e.g., SPARC, specific ARM configs). Struct size matches optimized access width (e.g., 8 bytes). Pointer alignment is lower than type assumed alignment.

**Mitigation**
Add __packed __aligned(N) attributes to struct definition to match actual runtime alignment guarantees and prevent optimized aligned loads.

---

## Code Pattern

```json
{
  "triggers": [
    "Compiler optimization enabled",
    "Architecture requires strict alignment",
    "Pointer alignment less than type assumed alignment",
    "Struct copy or memory access of fixed width"
  ],
  "vulnerable_pattern": "A memory access operation (struct copy, memcpy, or load) involving a struct type that lacks explicit alignment attributes, where the accessed pointer may have lower alignment than the type's default alignment assumption used by the optimizer for generating aligned instructions.",
  "ql_constraints": "Identify StructType definitions lacking explicit AlignmentAttribute. Find AccessExpressions or CallExpressions (memcpy) using pointers to this type. Check if AccessSize allows optimized aligned instruction generation (e.g., 8 bytes). Trace PointerSource to identify potential lower alignment origins (e.g., void* cast, network buffer, packed struct member). Link Type definition to Access site via Pointer Type.",
  "equivalence_notes": [
    "Struct assignment and memcpy are equivalent memory operations",
    "Direct load/store and library calls are equivalent if optimized similarly",
    "__packed and __aligned attributes control alignment semantics",
    "Pointer dereference and array access are equivalent regarding alignment"
  ],
  "scope_assumptions": [
    "Access occurs within the same function or via passed pointer",
    "Type definition is visible to the compiler at access site"
  ],
  "control_flow_assumptions": [
    "Access occurs after pointer derivation",
    "No intervening alignment correction before access"
  ],
  "environment_assumptions": [
    "Compiler optimization level > 0",
    "Target architecture has strict alignment requirements",
    "Compiler defaults to natural alignment unless specified"
  ]
}
```

---

## Provenance

- Source analysis: /home/suiren/cisb-llm/results/kernel/P/04ef0f1a01_analysis.md
- Source id: 04ef0f1a01
- Digest: available
- Generated at: 2026-05-01T13:26:09.675439+00:00
- Model: qwen3.5-397b-a17b
