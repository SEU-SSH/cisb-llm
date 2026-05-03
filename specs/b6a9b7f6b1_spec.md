# CISB Specification

## Vulnerability Description

**Source**
Linux kernel commit; GCC 4.8.0-1 on s390x; mm/mmap.c and mm/nommu.c find_vma()

**Description**
Compiler optimization removes local variable cache in find_vma(), causing mm->mmap_cache to be re-read from memory instead of using the cached local variable. This creates a race condition where concurrent threads can observe stale pointer values, leading to kernel BUG and potential memory corruption.

**Evidence**
GCC 4.8.0-1 optimizes away local variable vma assignment, transforming single read of mm->mmap_cache into multiple memory reads. Concurrent thread access causes inconsistent VMA pointer values, triggering kernel BUG at mm/rmap.c:1088 during mallocstress testing.

**Requirement**
GCC 4.8.0-1 or similar optimization behavior; s390x architecture (reported); kernel context with concurrent mm_struct access; default optimization levels that enable variable elimination

**Mitigation**
Use ACCESS_ONCE() macro to enforce atomic single read of shared memory location; alternatively use volatile qualifier or compiler barrier to prevent optimization of local variable cache

---

## Code Pattern

```json
{
  "triggers": [
    "Compiler optimization eliminates local variable cache",
    "Shared memory location accessed without memory barrier",
    "Concurrent thread access to same mm_struct",
    "Multiple implicit reads of same memory location after optimization"
  ],
  "vulnerable_pattern": "Local variable assigned from shared memory location (vma = mm->mmap_cache), then used for null check and subsequent field access. Without memory barrier annotation, compiler may optimize away the local variable and re-read from memory, causing race condition with concurrent writers.",
  "ql_constraints": "Match assignment from field/member access to local variable; track subsequent uses of that variable for null checks and dereferences; identify missing volatile/ACCESS_ONCE/barrier on the read source; link same memory object across multiple read sites after optimization; prefer data-flow relation over exact AST matching",
  "equivalence_notes": [
    "EXPR == NULL, EXPR == 0, !EXPR normalize to isNull(EXPR)",
    "EXPR != NULL, EXPR != 0, !!EXPR, if(EXPR) normalize to isNonNull(EXPR)",
    "*ptr, ptr->field, (*ptr).field treated as dereference family",
    "Declaration initialization and later assignment treated as equivalent value sources",
    "ACCESS_ONCE(), READ_ONCE(), volatile read treated as memory barrier family"
  ],
  "scope_assumptions": [
    "Within the same function",
    "Local variable and shared memory field in same scope"
  ],
  "control_flow_assumptions": [
    "Assignment precedes null check",
    "Null check precedes dereference/access",
    "No intervening writes to the local variable between assignment and use"
  ],
  "environment_assumptions": [
    "Compiler optimization enabled that eliminates local variable cache",
    "Concurrent access to shared memory location possible",
    "No hardware memory barriers preventing re-ordering"
  ]
}
```

---

## Provenance

- Source analysis: /home/suiren/cisb-llm/results/kernel/P/b6a9b7f6b1_analysis.md
- Source id: b6a9b7f6b1
- Digest: available
- Generated at: 2026-05-01T13:54:51.447949+00:00
- Model: qwen3.5-397b-a17b
