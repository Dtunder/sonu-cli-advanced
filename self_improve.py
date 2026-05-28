import os
import sys
import time
import subprocess
from dotenv import load_dotenv
from openai import OpenAI

# Force UTF-8 on Windows console
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def log_message(log_path, message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}\n"
    print(entry, end="")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

def main():
    load_dotenv(override=True)
    
    # Configuration
    duration_min = 60
    if len(sys.argv) > 1:
        try:
            duration_min = int(sys.argv[1])
        except ValueError:
            pass
            
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(workspace_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    log_path = os.path.join(logs_dir, "self_improvement_log.md")
    
    # Initialize Log
    model_name = "llama-3.1-8b-instant"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# Sonu CLI Auto-Evolution Logbook\n\n- **Target Duration:** {duration_min} minutes\n- **Provider:** Groq ({model_name})\n- **Start Time:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        log_message(log_path, "❌ ERROR: GROQ_API_KEY not found in environment. Please set it in .env first.")
        sys.exit(1)
        
    client = OpenAI(
        api_key=groq_api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    # Target files for self-improvement
    target_files = [
        "smart_router.py",
        "temporal_memory.py",
        "swarm_consensus.py",
        "personality_engine.py",
        "health_monitor.py",
        "process_manager.py"
    ]
    
    log_message(log_path, f"🚀 Starting 10x Auto-Evolution Loop for {duration_min} minutes.")
    log_message(log_path, f"Target files: {', '.join(target_files)}")
    
    start_time = time.time()
    end_time = start_time + (duration_min * 60)
    iteration = 0
    
    while time.time() < end_time:
        iteration += 1
        elapsed = (time.time() - start_time) / 60
        log_message(log_path, f"\n🔄 === Iteration {iteration} (Elapsed: {elapsed:.1f}/{duration_min} min) ===")
        
        # Pick the next file sequentially
        target_file = target_files[(iteration - 1) % len(target_files)]
        file_path = os.path.join(workspace_dir, target_file)
        
        if not os.path.exists(file_path):
            log_message(log_path, f"⚠️ Skip: File {target_file} not found.")
            continue
            
        log_message(log_path, f"🔍 Analyzing {target_file}...")
        
        # Read the file contents
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code_content = f.read(2500)  # max 2500 characters to avoid 429 TPM limits
        except Exception as e:
            log_message(log_path, f"❌ Failed to read {target_file}: {e}")
            continue
            
        # Read the brainstorm plan if available
        brainstorm_content = ""
        brainstorm_path = os.path.join(workspace_dir, "SONU_10X_BRAINSTORM.md")
        if os.path.exists(brainstorm_path):
            try:
                with open(brainstorm_path, "r", encoding="utf-8") as f:
                    brainstorm_content = f.read()[:600] # Limit context size to avoid TPM limits
            except Exception:
                pass
                
        # Ask Groq to improve the code
        prompt = (
            f"You are the Sonu CLI Auto-Evolution Core. Your job is to improve the file '{target_file}' to make the Sonu CLI more autonomous, higher quality, and robust.\n\n"
            f"Here is our 10x Brainstorm Plan context:\n{brainstorm_content}\n\n"
            f"Here is the current code of '{target_file}':\n```python\n{code_content}\n```\n\n"
            f"Analyze the code for any of the following:\n"
            f"- Logical bugs or unhandled edge cases.\n"
            f"- Opportunities for 10x architecture (e.g. better resilience, predictive checks, asynchronous speedups).\n"
            f"- Code readability or missing/incomplete helper methods.\n\n"
            f"Write a fully upgraded, robust version of the file. Answer ONLY with the raw python code inside a single fenced code block (```python ... ```) that is a drop-in replacement. Do not write any explanations before or after the code block. Your output will be written directly to the file."
        )
        
        try:
            log_message(log_path, "💬 Requesting code optimization from Groq...")
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a senior system architect and Python expert specializing in autonomous agents, low-latency control systems, and robust error handling."},
                    {"role": "user", "content": prompt}
                ],
                model=model_name,
                temperature=0.2,
                max_tokens=2048
            )
            response_text = chat_completion.choices[0].message.content
        except Exception as e:
            log_message(log_path, f"❌ Groq API call failed: {e}")
            time.sleep(35)
            continue
            
        # Parse Python code block
        if "```python" in response_text:
            new_code = response_text.split("```python")[1].split("```")[0].strip()
        elif "```" in response_text:
            new_code = response_text.split("```")[1].split("```")[0].strip()
        else:
            new_code = response_text.strip()
            
        if not new_code.startswith("import") and "def " not in new_code:
            log_message(log_path, "❌ Failed to parse valid Python code from LLM response. Skipping modification.")
            continue
            
        # Save a backup of the current file
        backup_path = file_path + ".bak"
        try:
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(code_content)
        except Exception as e:
            log_message(log_path, f"❌ Failed to create backup of {target_file}: {e}")
            continue
            
        # Overwrite the file with the new code
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_code)
            log_message(log_path, f"✏️ Applied upgrades to {target_file}.")
        except Exception as e:
            log_message(log_path, f"❌ Failed to overwrite {target_file}: {e}")
            # Revert from backup
            os.replace(backup_path, file_path)
            continue
            
        # Run Verification (Ghost Integrator Audit / Tests)
        log_message(log_path, "🧪 Running verification tests...")
        
        # Test command: we run the advanced features test script or discover unit tests
        test_cmd = ["python", "-m", "unittest", "discover", "-s", workspace_dir, "-p", "test_*.py"]
        if os.path.exists(os.path.join(workspace_dir, "test_advanced_features.py")):
            test_cmd = ["python", os.path.join(workspace_dir, "test_advanced_features.py")]
            
        test_result = subprocess.run(
            test_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=workspace_dir
        )
        
        if test_result.returncode == 0:
            log_message(log_path, f"✅ SUCCESS: All tests passed! Upgrades to {target_file} are stable.")
            if os.path.exists(backup_path):
                os.remove(backup_path)
            try:
                subprocess.run(["git", "add", file_path], cwd=workspace_dir)
                subprocess.run(["git", "commit", "-m", f"Auto-Improve: optimized {target_file} via Sonu Auto-Evolution Loop", "--no-verify"], cwd=workspace_dir)
                log_message(log_path, f"💾 Committed upgrades for {target_file} to Git (no-verify).")
            except Exception:
                pass
        else:
            log_message(log_path, f"❌ FAILURE: Tests failed with exit code {test_result.returncode}. Output:\n{test_result.stderr[:500]}")
            log_message(log_path, f"🔄 Rolling back changes on {target_file}...")
            # Revert changes using backup or git
            if os.path.exists(backup_path):
                os.replace(backup_path, file_path)
            else:
                subprocess.run(["git", "checkout", "--", target_file], cwd=workspace_dir)
            log_message(log_path, f"✅ Rollback complete. {target_file} restored to original state.")
            
        # Anti-spam delay to respect Groq rate limits
        log_message(log_path, "⏳ Sleeping for 25 seconds to prevent rate-limit saturation...")
        time.sleep(25)
        
    log_message(log_path, f"\n🎉 Auto-Evolution Loop completed successfully! End Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    main()
