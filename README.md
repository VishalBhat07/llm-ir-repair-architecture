# llm-ir-repair-architecture

**Investigating neural compiler lowering, structural failure modes, and automated validation loops.**

---

## 01. Overview
This project evaluates the efficacy of Large Language Models (LLMs) in translating high-level source language constructs into structured **LLVM Intermediate Representation (IR)**. Unlike standard code generation, compiler IR requires strict adherence to **Static Single Assignment (SSA)** rules, type invariants, and control-flow integrity. 

The core of this architecture is a **validator-in-the-loop** system that uses formal compiler tools to audit neural outputs and trigger automated repairs.



---

## 02. Objectives
The research aims to determine if an LLM can:
* **Map** basic high-level constructs (arithmetic, conditionals, loops) to valid IR.
* **Preserve** complex data-flow and control-flow structures without semantic drift.
* **Recover** from generation errors using feedback from the LLVM `opt` verifier.
* **Categorize** failure modes specific to neural lowering (e.g., dominance violations).

---

## 03. Project Architecture

### The Pipeline
1.  **Ingestion:** A subset of C-language constructs is provided as input.
2.  **Neural Lowering:** The LLM acts as the compiler frontend, generating LLVM IR.
3.  **Auditing:** The IR is passed through `opt -S -verify` (LLVM 22.1.3).
4.  **Repair Loop:** Error logs (stderr) are fed back to the LLM for iterative correction until the IR is semantically valid.

---

## 04. Repository Structure

```text
llm-ir-repair-architecture/
├── benchmarks/         # Source C snippets (the "Input")
├── ground_truth/       # Clang-generated reference IR (the "Gold Standard")
├── src/
│   ├── driver.py       # Automation harness & Repair Loop logic
│   ├── llm_client.py   # LLM API integration (Gemini / Ollama)
│   └── validator.py    # Subprocess wrapper for LLVM 'opt'
├── results/            # Logs of raw LLM output vs. verified IR
└── FAILURE_MODES.md    # Catalog of identified neural compiler errors
```

---

## 05. Technical Stack

| Component | Specification |
| :--- | :--- |
| **Host Hardware** | MacBook Air M2 (8GB RAM) |
| **Compiler Suite** | LLVM 22.1.3 |
| **Automation** | Python 3.11+ |
| **LLM Engine** | Gemini 1.5 Flash / Gemini 3.1 Pro |

---

## 06. Failure Taxonomy
This project tracks and categorizes specific neural failures including:

* **SSA Violations:** Re-assignment of virtual registers.
* **Dominance Errors:** Use-before-definition in the Control-Flow Graph (CFG).
* **Type Invariants:** Operations on incompatible bit-widths without casting.
* **Terminator Errors:** Basic blocks lacking proper `br` or `ret` instructions.

---

## 07. Usage
1.  **Install LLVM:** `brew install llvm`
2.  **Clone Repo:** `git clone https://github.com/VishalBhat07/llm-ir-repair-architecture.git`
3.  **Run Pipeline:** `python src/driver.py`

---

## 08. Acknowledgments
Developed for **CS363IA: Compiler Design** (Semester VI) at **RV College of Engineering**. This project explores the boundary between deterministic compiler engineering and probabilistic neural generation.

---
