# LLM IR Repair Architecture

Research framework for studying whether LLMs can lower a constrained high-level language subset into **valid LLVM IR**, where they fail, and how much a validator-and-repair loop helps.

## What This Repository Now Covers

- A fixed LLVM-focused lowering study rather than a single hardcoded demo
- A benchmark corpus with **18 cases**
  - `10` curated core programs
  - `8` mutated variants
- A multi-backend model interface for:
  - local `Ollama`
  - hosted `Gemini`
- A staged validator pipeline:
  - output sanitization
  - `llvm-as` parse gate
  - `opt -passes=verify`
  - custom structural failure labeling
  - semantic execution with `lli`
- A bounded repair loop that feeds diagnostics back into the model
- Batch experiment running plus CSV/JSON/Markdown reporting

## Repository Layout

```text
llm-ir-repair-architecture/
├── benchmarks/
│   ├── core/                 # Curated source programs
│   ├── mutated/              # Systematic program variants
│   ├── invalid_ir/           # Seeded invalid LLVM IR fixtures
│   └── metadata/             # Benchmark manifests with tags and tests
├── configs/
│   └── models.yaml           # JSON-compatible YAML model suite config
├── docs/
│   ├── lowering_matrix.md
│   ├── environment.md
│   └── future_fine_tuning.md
├── ground_truth/             # Clang-generated reference IR
├── results/                  # Experiment outputs
├── src/
│   ├── driver.py             # CLI entrypoint
│   ├── validator.py          # Backward-compatible wrapper
│   └── llm_ir_pipeline/      # Core package
└── tests/
```

## Benchmark Design

The source subset intentionally focuses on the places LLMs commonly fail when generating compiler IR:

- integer arithmetic
- comparisons
- assignments and reassignment pressure
- `if` / `if-else` / nested branches
- `for` and `while` loops
- loop-carried values
- helper function calls
- early returns
- branch-merge patterns that usually require `phi` nodes after lowering

Out of scope in v1:

- pointers
- structs
- heap memory
- floating point
- recursion
- undefined-behavior-heavy C patterns

## Model Matrix

The default model suite in `configs/models.yaml` includes:

- `qwen25_coder_small_local`
- `gemini_api`

You can add or remove models without changing the rest of the pipeline.
`qwen25_coder_small_local` is configured for Ollama `qwen2.5-coder:3b`.

## Validation and Repair Flow

1. Prompt a model to lower a benchmark source program into LLVM IR.
2. Sanitize the raw output to remove markdown and conversational text.
3. Parse with `llvm-as`.
4. Verify structural correctness with `opt -passes=verify`.
5. Run custom checks to classify failure modes such as:
   - duplicate SSA names
   - undefined values
   - malformed `phi`
   - bad labels
   - missing terminators
   - signature mismatches
   - type-width mismatches
6. If available, execute the IR with `lli` on public and hidden test vectors.
7. If validation fails, feed precise diagnostics into a repair prompt and retry.

## CLI Usage

Run commands from the repository root.

### Check the environment

```bash
python src/driver.py smoke-test
```

### Inspect the benchmark inventory

```bash
python src/driver.py inventory
```

### Generate reference LLVM IR with Clang

```bash
python src/driver.py prepare-ground-truth
```

Limit to a split:

```bash
python src/driver.py prepare-ground-truth --splits core,mutated
```

### Run experiments

```bash
python src/driver.py run --models qwen25_coder_small_local --splits core --prompt zero_shot --repair-attempts 1
```

If you omit `--models`, the CLI defaults to running all models defined in the yaml file.

By default, `--repair-attempts 1` runs the zero-shot generation with no repair. If you want the system to pipe compiler diagnostics back into the LLM if it fails and give it multiple chances to fix its mistakes, set `--repair-attempts 3`.

Few-shot condition:

```bash
python src/driver.py run --models gemini_api --splits core --prompt few_shot --limit 10
```

Artifacts are written into timestamped subdirectories under `results/`.

## Environment Setup

Because this pipeline compiles the generated `.ll` files directly into `.exe` or `.out` binaries to perform rigorous semantic validation, you must have full LLVM and C++ linking tools on your `PATH`.

- Python 3.11+
- `clang`

You can verify your toolchain by running `python src/driver.py smoke-test`. The script gracefully falls back to `clang` to perform all parsing and semantic evaluations if native `llvm-as` and `lli` are missing.

### 🐛 Windows MSVC Linker Troubleshooting
If you attempt to run on Windows in a standard PowerShell, `clang` will fail to compile the executables with the error: `lld-link: error: could not open 'libcmt.lib'`.
**The Fix:** You must run the `src/driver.py` command from inside the **"x64 Native Tools Command Prompt for VS"** (search for this in the Windows Start Menu). This automatically injects the Microsoft C++ Linker tools into the terminal's environment, allowing `clang` to execute properly.

Alternatively, use the intended research environment: **WSL2 Ubuntu**.

## Report and Paper Guidance

The pipeline is designed to support the assignment deliverables directly:

- a defined source-language subset
- a target-IR mapping and lowering matrix
- generated IR examples plus correctness analysis
- failure-mode categorization
- validator / repair architecture
- comparative evaluation across Ollama and Gemini models

Recommended headline metrics:

- parse pass rate
- verifier pass rate
- semantic pass rate
- repair uplift
- attempts to success
- latency
- token usage
- estimated cost

Recommended ablations:

- zero-shot vs few-shot
- raw generation vs repair loop
- sanitizer on vs off
- validator feedback on vs off

## Official References For Model Access

- Gemini API quickstart: https://ai.google.dev/gemini-api/docs/quickstart
- Ollama docs: https://docs.ollama.com/
