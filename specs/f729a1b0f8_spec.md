# CISB Specification

## Vulnerability Description

**Source**
f729a1b0f8 - Linux kernel commit fixing struct input_event padding on sparc64

**Description**
On sparc64 architecture, the compiler automatically adds padding after the __usec field in struct input_event for alignment. The original struct definition did not account for this implicit padding, causing layout divergence from glibc timeval definition. Individual field assignments in evdev.c and uinput.c did not initialize padding bytes, allowing uninitialized kernel stack data to leak to user space when events were copied.

**Evidence**
Compiler's implicit padding created struct layout mismatch. Individual field assignments (type, code, value, sec, usec) left padding bytes uninitialized. When struct was copied to user space via client buffer or uinput buffer, uninitialized padding containing kernel stack data was exposed.

**Requirement**
sparc64 architecture (__sparc__ && __arch64__), kernel code with struct copied to user space, optimization level that preserves struct padding behavior

**Mitigation**
Use C99 designated struct initializer instead of individual field assignments to ensure all fields including padding are zero-initialized. Add explicit __pad field to struct definition to match expected layout. Use compiler options to control struct packing if appropriate.

---

## Code Pattern

```json
{
  "triggers": [
    "Architecture-specific struct padding behavior (sparc64)",
    "Individual field assignments instead of struct initializer",
    "Struct copied to user space without explicit padding initialization",
    "Compiler implicit padding not accounted for in struct definition"
  ],
  "vulnerable_pattern": "struct S with architecture-dependent padding; individual field assignments to struct instance (field1 = val1; field2 = val2; ...); struct instance copied to user-visible buffer without explicit padding initialization; padding bytes remain uninitialized and may contain sensitive data",
  "ql_constraints": "Link struct definition to architecture-specific padding behavior; identify individual field assignment sequences to same struct instance; detect struct copy operations to user-space visible buffers; ensure padding initialization status is tracked; match equivalent forms: direct assignment vs initializer list, array copy vs memcpy, explicit field access vs pointer dereference",
  "equivalence_notes": [
    "struct.field = value and ptr->field = value are equivalent field assignments",
    "C99 designated initializer { .field = value } and individual assignments are semantically different for padding initialization",
    "struct copy via assignment, memcpy, or buffer copy are equivalent for data exposure",
    "NULL check forms: EXPR == NULL, EXPR == 0, !EXPR normalize to isNull(EXPR)",
    "Dereference forms: *ptr, ptr->field, (*ptr).field normalize to same access family"
  ],
  "scope_assumptions": [
    "Struct definition and usage within same kernel module or linked compilation unit",
    "Field assignments and struct copy occur in same function or through same argument chain"
  ],
  "control_flow_assumptions": [
    "Field assignments complete before struct is copied to user-visible buffer",
    "No intervening initialization of padding bytes between field assignments and copy operation"
  ],
  "environment_assumptions": [
    "sparc64 architecture with compiler implicit padding behavior",
    "Kernel code with user-space data exposure path",
    "Struct layout must match user-space expectation (glibc timeval definition)"
  ]
}
```

---

## Provenance

- Source analysis: /home/suiren/cisb-llm/results/kernel/P/f729a1b0f8_analysis.md
- Source id: f729a1b0f8
- Digest: available
- Generated at: 2026-05-01T13:59:44.647801+00:00
- Model: qwen3.5-397b-a17b
