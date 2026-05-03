# CISB Specification

## Vulnerability Description

**Source**
Kernel Commit 94f6bac105 / GCC 3.4.6 Optimization Bug

**Description**
GCC 3.4.6 incorrectly optimizes consecutive calls to a static inline function (have_cpuid_p) that depends on hardware state modified by an intervening function (c_identify). The compiler assumes the helper function (flag_is_changeable_p) is pure due to missing memory clobbers in its inline assembly, merging calls and causing missed CPU feature detection.

**Evidence**
Source code contains two distinct calls to have_cpuid_p() separated by c_identify(). Compiled code merges them into one call or reuses the first result. Runtime behavior shows CPUID features (ARR registers) not detected on Cyrix CPUs due to stale flag evaluation.

**Requirement**
GCC 3.4.6 or similar optimizing compiler, x86 architecture, optimization enabled (default), static inline functions containing inline assembly without memory clobbers.

**Mitigation**
Add a memory clobber ("memory") to the inline assembly clobber list in the helper function (flag_is_changeable_p) to prevent the compiler from assuming no memory or state side effects.

---

## Code Pattern

```json
{
  "triggers": [
    "Compiler merges consecutive calls to static inline function",
    "Inline assembly lacks memory clobber indicating state dependency",
    "Intervening code modifies hardware state visible to the assembly"
  ],
  "vulnerable_pattern": "A static inline function wrapping inline assembly without a memory clobber is called multiple times within the same control flow path, separated by operations that modify hardware state visible to the assembly, allowing the compiler to eliminate subsequent calls via common subexpression elimination.",
  "ql_constraints": "Identify FunctionDefinition containing InlineAsmStmt. Verify InlineAsmStmt clobber list does not contain 'memory'. Identify multiple CallSite nodes targeting this FunctionDefinition within the same CFG. Verify a control flow path exists between CallSites without intervening volatile assembly or explicit memory barriers.",
  "equivalence_notes": [
    "Inline assembly without memory clobber is equivalent to pure function from optimizer perspective",
    "Static inline function wrapping asm is equivalent to direct asm block",
    "Missing 'memory' clobber is equivalent to missing 'volatile' keyword on asm in this context"
  ],
  "scope_assumptions": [
    "Within the same function scope after inlining",
    "Calls must be visible to the optimizer (static inline)"
  ],
  "control_flow_assumptions": [
    "Sequential execution path exists between the two calls",
    "No explicit compiler barriers exist between the calls"
  ],
  "environment_assumptions": [
    "GCC compiler",
    "Optimization level greater than O0",
    "x86 architecture"
  ]
}
```

---

## Provenance

- Source analysis: /home/suiren/cisb-llm/results/kernel/P/94f6bac105_analysis.md
- Source id: 94f6bac105
- Digest: available
- Generated at: 2026-05-01T13:51:16.085017+00:00
- Model: qwen3.5-397b-a17b
