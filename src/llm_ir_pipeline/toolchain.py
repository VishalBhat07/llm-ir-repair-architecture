from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .types import CommandResult, ToolchainStatus


class LLVMToolchain:
    def __init__(self) -> None:
        self._commands = {
            "clang": self._find_executable(["clang"]),
            "llvm_as": self._find_executable(["llvm-as", "llvm_as"]),
            "opt": self._find_executable(["opt"]),
            "lli": self._find_executable(["lli"]),
            "filecheck": self._find_executable(["FileCheck", "filecheck"]),
        }
        self.status = ToolchainStatus(
            clang=self._commands["clang"],
            llvm_as=self._commands["llvm_as"],
            opt=self._commands["opt"],
            lli=self._commands["lli"],
            filecheck=self._commands["filecheck"],
        )

    def has(self, tool_name: str) -> bool:
        return bool(getattr(self.status, tool_name))

    def command_for(self, tool_name: str) -> str | None:
        return getattr(self.status, tool_name)

    def run(self, command: list[str], cwd: Path | None = None) -> CommandResult:
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
            )
            return CommandResult(
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        except subprocess.TimeoutExpired as e:
            return CommandResult(
                command=command,
                returncode=-1,
                stdout=e.stdout.decode("utf-8") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                stderr=f"Execution timed out after 10 seconds: {e}",
            )

    def run_tool(self, tool_name: str, args: list[str], cwd: Path | None = None) -> CommandResult:
        command = self.command_for(tool_name)
        if not command:
            raise ValueError(f"Tool {tool_name} is not available")
        return self.run([command, *args], cwd=cwd)

    def _candidate_dirs(self) -> list[Path]:
        candidates: list[Path] = []
        llvm_bin = os.environ.get("LLVM_BIN")
        if llvm_bin:
            candidates.append(Path(llvm_bin))
        clang_path = shutil.which("clang")
        if clang_path:
            candidates.append(Path(clang_path).parent)
        candidates.append(Path(r"C:\Program Files\LLVM\bin"))

        deduped: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate).lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    def _find_executable(self, names: list[str]) -> str | None:
        for name in names:
            found = shutil.which(name)
            if found:
                return found
            if os.name == "nt" and not name.lower().endswith(".exe"):
                found = shutil.which(f"{name}.exe")
                if found:
                    return found

        suffixes = ["", ".exe"] if os.name == "nt" else [""]
        for directory in self._candidate_dirs():
            for name in names:
                for suffix in suffixes:
                    candidate = directory / f"{name}{suffix}"
                    if candidate.exists():
                        return str(candidate)
        return None

    def smoke_test(self) -> dict[str, object]:
        report: dict[str, object] = {"tools": self.status.as_dict(), "commands": {}}
        versions = {
            "clang": ["--version"],
            "llvm_as": ["--version"],
            "opt": ["--version"],
            "lli": ["--version"],
            "filecheck": ["--version"],
        }
        for key, args in versions.items():
            if not self.has(key):
                report["commands"][key] = {"available": False}
                continue
            result = self.run_tool(key, args)
            report["commands"][key] = {
                "available": result.ok,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        return report
