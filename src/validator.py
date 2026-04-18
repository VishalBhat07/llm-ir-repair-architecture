import subprocess

def check_ir_validity(ir_filepath):
    """
    Runs the LLVM 'opt' tool with the -verify flag.
    Returns (True, None) if valid.
    Returns (False, error_message) if invalid.
    """
    try:
        # -S: Keep it human-readable
        # -verify: The critical check for SSA and structural integrity
        # Use the '-passes' flag which is required by the New Pass Manager in LLVM 22+
        # We use '-disable-output' because we only care about the validation result, not printing the IR.
        cmd = ["opt", "-passes=verify", "-disable-output", ir_filepath]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True, "Success"
        else:
            return False, result.stderr
    except FileNotFoundError:
        return False, "LLVM 'opt' not found in PATH."