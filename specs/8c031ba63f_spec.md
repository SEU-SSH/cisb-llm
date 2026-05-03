# CISB Specification

## Vulnerability Description

**Source**
Commit 8c031ba63f

**Description**
gcc-7 optimizes byte-wise accesses of external variables declared with aligned types (e.g., __le32) into word-wise accesses, ignoring potential unaligned addresses determined by linker scripts. This causes unaligned access faults on architectures like PARISC.

**Evidence**
Compiler transforms get_unaligned_le32() calls or dereferences of extern __le32 variables into word-load instructions. Runtime panic occurs on unaligned addresses. Fix adds __aligned(1) to declaration.

**Requirement**
gcc-7 or later, optimization enabled (-O2/-Os), architecture with strict alignment enforcement (e.g., PARISC).

**Mitigation**
Add __aligned(1) attribute to the variable declaration to force byte alignment and prevent word-wise optimization.

---

## Code Pattern

```json
{
  "triggers": [
    "Optimization level -O2 or -Os",
    "External variable declaration",
    "Type alignment > 1",
    "Missing explicit alignment attribute"
  ],
  "vulnerable_pattern": "An external variable is declared with a type that implies natural alignment greater than one byte, but the variable's actual address may be unaligned due to linker script placement. The compiler optimizes accesses based on the declared type alignment, ignoring the potential unalignment, leading to hardware faults on strict-alignment architectures.",
  "ql_constraints": "Select VariableDeclaration nodes with extern storage class. Filter where Type alignment requirement exceeds 1 byte. Exclude declarations having aligned(1) or packed attributes. Correlate with MemoryAccess expressions targeting the declared variable.",
  "equivalence_notes": [
    "__aligned(1)",
    "__attribute__((aligned(1)))",
    "__attribute__((packed))",
    "get_unaligned_le32",
    "get_unaligned"
  ],
  "scope_assumptions": [
    "Declaration and usage within the same translation unit or linked context"
  ],
  "control_flow_assumptions": [],
  "environment_assumptions": [
    "Architecture enforces alignment traps",
    "Linker script may place variable at unaligned address"
  ]
}
```

---

## Provenance

- Source analysis: /home/suiren/cisb-llm/results/kernel/P/8c031ba63f_analysis.md
- Source id: 8c031ba63f
- Digest: available
- Generated at: 2026-05-01T13:50:00.785504+00:00
- Model: qwen3.5-397b-a17b
