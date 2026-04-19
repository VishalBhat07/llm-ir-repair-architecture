# LLVM IR Lowering Matrix

This project evaluates LLM-assisted lowering for a constrained C-like subset. The goal is not to mimic all of Clang, but to stress the invariants that make LLVM IR difficult to generate correctly.

## Supported Source Subset

| Construct family                     | Included in v1 | Notes                                                                                  |
| :----------------------------------- | :------------- | :------------------------------------------------------------------------------------- |
| Integer scalars (`int`)              | Yes            | All values are modeled as `i32` unless a benchmark states otherwise.                   |
| Arithmetic expressions               | Yes            | `add`, `sub`, `mul`, `sdiv`, `srem` patterns are covered.                              |
| Comparisons                          | Yes            | `icmp` with signed integer predicates only.                                            |
| Assignments and reassignments        | Yes            | Important for detecting accidental SSA reuse.                                          |
| `if`, `if/else`, nested conditionals | Yes            | Benchmarks require correct block structure and merge behavior.                         |
| `for` loops                          | Yes            | Loop-carried variables and induction-variable updates are required.                    |
| `while` loops                        | Yes            | Header, body, and exit blocks must be explicit and typed correctly.                    |
| Helper functions and calls           | Yes            | Single and multi-argument integer functions only.                                      |
| Early returns                        | Yes            | Used to study control-flow shortening and block termination.                           |
| Pointers, arrays, heap, structs      | No             | Excluded to keep the study focused on structural lowering rather than memory modeling. |
| Floating point                       | No             | Excluded in v1 to keep typing and semantics tighter.                                   |
| Recursion                            | No             | Out of scope for the first report.                                                     |

## Lowering Expectations By Construct

| Source construct               | Expected LLVM IR pattern                                                     | Key invariants                                                             | Common LLM failure modes                                                  |
| :----------------------------- | :--------------------------------------------------------------------------- | :------------------------------------------------------------------------- | :------------------------------------------------------------------------ |
| Integer parameters and returns | `define i32 @f(i32 %a, i32 %b)`                                              | Every parameter used with the declared type; return type matches signature | Mismatched parameter count, wrong return type, undeclared parameter reuse |
| Pure arithmetic expression     | Single basic block with typed arithmetic instructions and `ret`              | Operand types match op type; SSA names are unique                          | Reusing `%1`, mixing `i1` and `i32`, emitting text explanations inline    |
| Comparison                     | `icmp` producing `i1`                                                        | Predicate must be valid for operand type                                   | Duplicated type tokens, using `icmp` result as `i32` without conversion   |
| `if/else`                      | Entry block with conditional `br`, then/else blocks, merge or direct returns | Every block terminates; branch targets exist                               | Missing terminator, dangling labels, invalid merge structure              |
| Nested branch                  | Multi-level conditional blocks                                               | Dominance and merge points must remain valid                               | Use-before-def, incorrect label reuse, missing nested merge labels        |
| Branch merge value             | `phi` in merge block or equivalent structured SSA                            | Incoming block labels align with predecessors                              | Malformed `phi`, wrong predecessor labels, extra incoming pairs           |
| `for` loop                     | Preheader, loop header, body, latch, exit                                    | Induction variable update dominates next use                               | Missing back-edge, incorrect `phi`, loop condition in wrong block         |
| `while` loop                   | Entry `br` to header, condition, body, exit                                  | Header dominates body and exit                                             | Header without terminator, duplicated labels, body falls through          |
| Loop-carried accumulator       | `phi` nodes for accumulator and induction variable                           | One incoming value per predecessor                                         | Accumulator updated outside SSA discipline, missing incoming edge         |
| Helper function call           | `call i32 @helper(i32 %x, ...)`                                              | Callee signature and arguments match exactly                               | Wrong arity, undeclared callee, type-width mismatch                       |
| Early return                   | Conditional block may `ret` directly                                         | No code after terminator in a block                                        | Unreachable instructions after `ret`, missing else-path terminator        |

## Benchmark Families

- `arithmetic`: Expression lowering, reassignment pressure, operator precedence.
- `compare`: Signed integer `icmp` correctness.
- `branch`: CFG construction and direct-return patterns.
- `loop`: Structured loops, loop-carried state, and `phi` placement.
- `function`: Signature preservation and helper-call correctness.
- `cfg`: Mixed control-flow patterns that commonly trigger dominance and terminator errors.

## Validation Strategy Mapping

| Validation stage                   | Purpose                                | What it catches                                                        |
| :--------------------------------- | :------------------------------------- | :--------------------------------------------------------------------- |
| Sanitizer                          | Normalize model text into candidate IR | Markdown fences, commentary, duplicate module preambles                |
| Parse gate (`llvm-as`)             | Syntactic well-formedness              | Tokenization errors, malformed headers, broken instruction syntax      |
| Verifier (`opt -passes=verify`)    | LLVM structural correctness            | SSA violations, dominance issues, invalid CFG, bad types               |
| Custom structural checks           | More precise failure labels            | Duplicate SSA names, bad `phi`, label drift, call signature mismatches |
| Semantic execution (`lli`/`clang`) | Behavioral correctness                 | Semantically wrong but verifier-clean IR                               |

## Report Guidance

- Report syntax, verifier, and semantic pass rates separately.
- Do not treat verifier success as proof of correct lowering.
- Compare zero-shot, few-shot, validator-only, and full repair-loop conditions.
- Break failure analysis down by construct family because loop and merge failures often dominate overall error rates.
