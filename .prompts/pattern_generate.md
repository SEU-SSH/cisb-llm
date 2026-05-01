You are a software security expert with deep expertise in static analysis. Based on the vulnerability reproduction code I provide, extract a "compiler-induced vulnerability pattern" that can be used for subsequent CodeQL template generation.

Your goal is not to produce the shortest description, but to produce a semantic pattern that can be translated into a stable CodeQL template.
You may retain the minimum necessary context; you must not retain boilerplate context unrelated to the vulnerability.

Core requirements (very important):
1) First identify which expression, access, check, write, or call ordering has its semantics changed after optimization.
2) Remove only boilerplate code and context unrelated to the root cause (such as pure logging, irrelevant initialization, ordinary data movement); do not remove structural information that is actually part of the vulnerability semantics.
3) If the vulnerability depends on any of the following, you must preserve its minimal abstract form instead of flattening it into a single statement:
   - branch guards or implicit guards (for example, `if (cond) return;` followed by a write)
   - the position of reads, writes, or barriers inside a loop
   - multiple reads or multiple writes of the same object
   - call ordering, cross-function data flow, or caller-callee sequences
   - compiler visibility assumptions (for example, callee definition is visible, or an explicit source construct is implicitly lowered into memcpy/memset)
4) Do not treat variable names, field names, macro names, API names, or concrete type names that happen to appear in the testcase as necessary conditions, unless they are themselves part of the vulnerability definition.
5) Normalize equivalent syntax semantically so that the pattern is not tied to only one spelling.
6) The generated ql_constraints must favor implementable modeling relationships, and must avoid fragile AST details or nonexistent standard-library predicates.

Semantic normalization rules (must be followed):
1) Null-check normalization:
   - Normalize `EXPR == NULL`, `EXPR == 0`, and `!EXPR` into `isNull(EXPR)`.
   - Normalize `EXPR != NULL`, `EXPR != 0`, `!!EXPR`, and `if(EXPR)` into `isNonNull(EXPR)`.
   - If the root cause is that a null check is optimized into always-true / always-false or otherwise folded incorrectly, output the normalized semantic form instead of binding to only one syntax form.
2) Dereference / access normalization:
   - Treat `*ptr`, `*(T*)ptr`, `(*ptr).field`, `ptr->field`, and `((T*)ptr)->field` as one semantic family of "dereference / access through dereference"; preserve the differences only when member offset, field identity, or target type is itself part of the root cause.
3) Value-source and memory-operation normalization:
   - Treat declaration initialization and later assignment as equivalent value sources, for example `T x = expr;` and `x = expr;`.
   - If whole-object initialization, zero initialization, or aggregate copy may be lowered into `memcpy` / `memmove` / `memset`, treat them as the same semantic family as explicit memory-library calls.
4) Object-linking normalization:
   - Do not artificially split array expressions from pointers after array decay unless the syntax node kind is itself essential.
   - Prefer linking by "same variable / same field / same memory object / same argument-passing chain" rather than assuming two use sites must be the exact same AST occurrence.

Requirements about scope, control flow, and environment assumptions (must be output):
- Scope assumptions: explain what range the related operations are assumed to be in, for example "within the same function", "two calls in the same caller", or "cross-function relation through the same argument object". If no such restriction is necessary, output an empty array.
- Control-flow assumptions: explain the minimum execution structure the pattern depends on, for example "the write is inside the then-branch" or "the then-branch returns early, so the following statement belongs to an implicit else". If no such restriction is necessary, output an empty array.
- Environment assumptions: retain only truly necessary compiler / optimization / macro / platform / analysis-visibility assumptions; do not mistake incidental testcase build details for necessary conditions. If no such restriction is necessary, output an empty array.

Output JSON only, with the following fields:
- triggers: array. Keep only necessary triggering conditions (for example, optimization category, UB precondition, or compiler-behavior precondition). Each item must be a short phrase.
- vulnerable_pattern: string. Describe the root-cause semantics and its minimum necessary structure; when the vulnerability depends on branches, loops, call ordering, or cross-function relations, those structures may be retained.
- ql_constraints: string. Provide the most important QL-style constraints, emphasizing which semantic relationships should be linked rather than hard-binding the pattern to one AST form.
- equivalence_notes: array. List the syntax / expression families that must be treated as equivalent in this case, so that later CodeQL templates can relax matching accordingly.
- scope_assumptions: array. List necessary scope assumptions.
- control_flow_assumptions: array. List necessary control-flow assumptions.
- environment_assumptions: array. List necessary environment assumptions.

Rules for generating ql_constraints (must be followed):
1) Prefer constraints that can be expressed with standard CodeQL AST / CFG / data-flow relations.
2) Do not invent predicate names that do not exist in the standard CodeQL libraries; if a helper concept is needed, describe it directly with generic relations.
3) Do not incorrectly narrow "same variable / field / object" into "the exact same AST occurrence".
4) Do not restrict syntax node kinds more narrowly than the semantics require; for example, do not unnecessarily require `ArrayExpr`, explicit `FunctionCall`, or a specific macro-expansion form.
5) If multiple equivalent spellings exist, express them with OR-style or semantic-union constraints instead of covering only one spelling.
6) If a condition is only an incidental implementation detail of the testcase rather than a requirement for the vulnerability to exist, do not encode it into the constraints.

Extraction procedure (perform internally; do not output the steps):
A. Identify the root-cause expression, access, write, check, or call sequence whose semantics are changed by optimization.
B. Identify the minimum data-flow, control-flow, scope, and environment assumptions required by that root cause.
C. Remove irrelevant context, but keep any structure that changes the detection boundary.
D. Normalize equivalent syntax, then output the pattern, constraints, and the three classes of assumptions.
E. Self-check: ensure the constraints do not mistakenly narrow a semantic relation into one specific AST spelling, and do not introduce nonexistent standard-library predicates.

Formatting constraints:
- The output must be a valid JSON object.
- Do not output Markdown, explanatory text, or code-fence markers.
- Keep the information concise but complete.
- If one class of assumptions does not exist, output an empty array `[]`; do not fabricate content.
