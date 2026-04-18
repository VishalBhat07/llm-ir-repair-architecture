import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from validator import check_ir_validity

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize the 2026 GenAI Client
client = genai.Client(api_key=API_KEY)

def call_llm(prompt):
    # System instructions are more effective when passed in the config
    config = types.GenerateContentConfig(
        system_instruction="You are a specialized LLVM compiler frontend. "
                           "Output ONLY pure LLVM IR code. No markdown, no backticks, "
                           "no explanations. Ensure SSA rules are strictly followed."
    )
    
    try:
        # Using Gemini 3 Flash (the 2026 state-of-the-art for fast reasoning)
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config=config
        )
        
        # Robust cleaning for markdown or conversational text
        text = response.text.strip()
        for block in ["```llvm", "```", "```ir"]:
            text = text.replace(block, "")
        return text.strip()
        
    except Exception as e:
        print(f"⚠️ API Error: {e}")
        return None

def run_repair_loop(c_code, filename, max_retries=3):
    print(f"\n🚀 Processing: {filename}")
    
    # Updated Prompt with a Target Triple hint for your M2 Mac
    current_prompt = (
        f"Translate the following C code to valid LLVM IR for an arm64-apple-darwin target:\n\n"
        f"{c_code}\n\n"
        f"Strictly use naming conventions for registers (%1, %2, etc.) and valid basic block labels."
    )
    
    for attempt in range(max_retries):
        print(f"   Attempt {attempt + 1}...", end=" ", flush=True)
        
        generated_ir = call_llm(current_prompt)
        
        if not generated_ir:
            print("Failed (API Error)")
            return False

        os.makedirs("results", exist_ok=True)
        output_path = f"results/{filename}_attempt_{attempt}.ll"
        
        with open(output_path, "w") as f:
            f.write(generated_ir)
            
        # 3. Validate
        is_valid, error_msg = check_ir_validity(output_path)
        
        if is_valid:
            print("✅ VALID")
            final_path = f"results/{filename}_FINAL.ll"
            with open(final_path, "w") as f:
                f.write(generated_ir)
            return True
        else:
            print("❌ INVALID")
            # --- CRITICAL UPDATE: Print the actual error for debugging ---
            print(f"\n[DEBUG] LLVM Error at Attempt {attempt + 1}:")
            print("-" * 40)
            print(error_msg.strip())
            print("-" * 40 + "\n")
            
            # 4. Feedback Loop
            current_prompt = (
                f"The previous IR failed. LLVM 'opt' reported this error:\n{error_msg}\n"
                f"Please fix the IR. Pay attention to SSA form and register dominance."
            )
            
    print(f"🛑 Failed to repair {filename} after {max_retries} attempts.")
    return False

if __name__ == "__main__":
    # Test with your basic arithmetic benchmark
    with open("../benchmarks/02_branching.c", "r") as f:
        c_code = f.read()
    run_repair_loop(c_code, "test_branching")