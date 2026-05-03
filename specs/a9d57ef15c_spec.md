# CISB Specification

## Vulnerability Description

**Source**
Linux Kernel Commit a9d57ef15c / GCC < 8.4.0

**Description**
GCC versions prior to 8.4.0 generate switch jump tables for switch statements with more than 20 cases. In the Linux kernel with CONFIG_RETPOLINE enabled, these jump tables produce indirect jumps that are not protected by retpoline mitigations, leaving them vulnerable to Spectre v2 branch target injection.

**Evidence**
Makefile modification adds -fno-jump-tables to KBUILD_CFLAGS under CONFIG_RETPOLINE. Report notes vmlinux size increase (0.27%) due to conversion from jump tables to conditional chains, confirming the removal of indirect jumps.

**Requirement**
GCC version < 8.4.0, CONFIG_RETPOLINE enabled, x86 architecture, default optimization settings (jump tables enabled).

**Mitigation**
Add compiler flag -fno-jump-tables, upgrade GCC to >= 8.4.0, or use Clang which disables jump tables by default under retpolines.

---

## Code Pattern

```json
{
  "triggers": [
    "GCC version < 8.4.0",
    "CONFIG_RETPOLINE enabled",
    "Switch statement with > 20 cases",
    "Missing -fno-jump-tables flag"
  ],
  "vulnerable_pattern": "A switch statement containing multiple case labels (historically > 20) compiled in a security-sensitive context (e.g., kernel with retpolines) without explicit disabling of jump table generation.",
  "ql_constraints": "Identify SwitchStatement nodes. Count associated CaseStatement labels. Flag if case count exceeds threshold (e.g., 20) AND project configuration implies retpoline usage without -fno-jump-tables. Link switch expression to potential indirect jump generation in lowered IR.",
  "equivalence_notes": [
    "Switch statement syntax",
    "Case label sequences",
    "Default label presence"
  ],
  "scope_assumptions": [
    "Within any function compiled with vulnerable flags"
  ],
  "control_flow_assumptions": [
    "Switch dispatch logic relies on indirect jump via jump table"
  ],
  "environment_assumptions": [
    "GCC compiler version < 8.4.0",
    "CONFIG_RETPOLINE defined",
    "-fno-jump-tables NOT present in compilation flags",
    "x86 architecture"
  ]
}
```

---

## Provenance

- Source analysis: /home/suiren/cisb-llm/results/kernel/P/a9d57ef15c_analysis.md
- Source id: a9d57ef15c
- Digest: available
- Generated at: 2026-05-01T13:54:29.092770+00:00
- Model: qwen3.5-397b-a17b
