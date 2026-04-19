# Environment and Tooling

## Recommended Runtime

- Host OS for research runs: **WSL2 Ubuntu** or **Docker**
- Python: 3.11+
- LLVM toolchain: `clang`, `llvm-as`, `opt`, `lli`, `FileCheck`
- Optional local inference:
  - `Ollama` on Windows, macOS, or Linux for easy local baselines

## Why WSL2 or Docker

The current Windows workspace does not have LLVM binaries on `PATH`, so verifier and semantic execution cannot run natively yet. The project is structured to make this explicit rather than silently downgrading validation.

## Suggested Docker Workflow

1. Build or pull an image containing LLVM 18+ and Python 3.11+.
2. Mount the repository into the container.
3. Install Python dependencies from `requirements.txt`.
4. Generate ground-truth IR with the provided preparation script.
5. Run smoke tests and then launch experiments.

## Suggested WSL2 Workflow

1. Install Ubuntu in WSL2.
2. Install LLVM and Clang using the Ubuntu package manager.
3. Install Python 3.11+ and project dependencies.
4. Export API keys only inside the WSL environment.
5. Run `python src/driver.py smoke-test` before experiments.

## Model Access Notes

- `Ollama` local runs assume a server on `http://localhost:11434`.
- Gemini access uses `GEMINI_API_KEY`.

## Fine-Tuning

Fine-tuning is intentionally out of scope for the core implementation. The pipeline still logs high-quality prompt/output/eval triples so that a future fine-tuning experiment can reuse the same dataset and validators.
