# Assignment 15: AI-Assisted Compiler Lowering Research Roadmap

This document outlines a strategy to elevate your current pipeline from a standard class assignment into a **research-paper-quality** deliverable. We will focus on establishing baseline metrics, defining novel repair architectures, and strictly analyzing the LLM's compiler knowledge boundaries.

## 1. Establishing the Research Baselines (The "Control" Group)

To write a strong paper, you cannot just present a final working model. You must prove *why* the pipeline is necessary.

*   **Experiment A (Zero-Shot Direct Lowering):** Pass C-code directly to the LLM and ask for LLVM IR with zero constraints or tools.
*   **Result Mapping:** You will likely see ~10% success on simple arithmetic and 0% on complex loops due to SSA rule breakage (which we already observed). 
*   *This satisfies deliverable (c) and the first half of (d).*

## 2. Novel "Better than Traditional" Architectures

To make this research-paper worthy, your proposed validator/repair architecture must go beyond merely feeding `clang` errors back into the prompt (which is generic and traditional). I propose testing the following **three advanced methods**:

### Method 1: Iterative Step-Lowering (Chain of Thought via Dialects)
*   **The Idea:** LLMs struggle with the massive semantic gap between C-like code and flat LLVM IR.
*   **The Architecture:** Force the LLM to generate an intermediary representation first (like an AST dump or MLIR-style structured loop dialect) before finalizing the LLVM SSA form. 
*   **Why it's better:** It prevents the LLM from getting "lost" tracking SSA variable states (`%1`, `%2`) across complex `if/else` boundaries.

### Method 2: RAG-Enriched Validation (Injecting LLVM LangRef)
*   **The Idea:** Generic `clang` compiler errors (e.g., "expected value token") do not give the LLM enough context on *how* to fix the rule it broke.
*   **The Architecture:** When `validator.py` catches an error, it doesn't just pass the error text. It uses a Retrieval-Augmented Generation (RAG) mapping to look up the exact LLVM Language Reference manual rule for that specific opcode (e.g., `phi`, `mul`) and injects the official LLVM documentation constraint into the repair prompt.
*   **Why it's better:** It directly targets the problem of LLMs hallucinating deprecated or invalid LLVM IR syntaxes.

### Method 3: Constrained Decoding (Grammar-enforced Generation)
*   **The Idea:** LLMs fail structural checks (missing terminators, malformed headers) constantly. 
*   **The Architecture:** Use a grammar enforcement tool (like `llama.cpp` grammar rules or `Outlines` library) to physically restrict the LLM from outputting tokens that violate LLVM IR syntax structures. 
*   **Why it's better:** It mathematically eliminates *structural and parse failures*, isolating the research exclusively to *semantic and data-flow failures*, which is a massive metric to report in a paper.

## 3. Categorization of Failure Modes (Deliverable D)

Your `FAILURE_MODES.csv` will be the centerpiece of the paper. We will write scripts to aggregate pipeline runs into these specific taxonomies:

1.  **Structural/Lexical Errors:** Extraneous markdown, missing `}`, invalid basic block names.
2.  **SSA Violations:** Reassigning a `%variable` twice, or using a `%var` before it is defined across a basic block boundary.
3.  **Control-Flow Graph (CFG) Errors:** Forgotten `ret` terminators at the end of `if/else` paths, or malformed `phi` nodes that don't cover all entry paths.
4.  **Semantic Hallucinations:** The IR compiles and passes the verifier, but executes the math completely wrong (e.g., computing `a - b` instead of `a + b`).
