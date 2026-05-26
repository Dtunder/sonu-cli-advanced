import sys
import argparse
import subprocess
import os

def run_research(query: str):
    print(f"--- RESEARCH AGENT ---")
    print(f"Goal: Deep dive into '{query}'")
    print(f"Simulating deep file search and analysis for {query}...")
    try:
        found = []
        for root, dirs, files in os.walk("."):
            if ".git" in root or "__pycache__" in root:
                continue
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if query.lower() in content.lower():
                            found.append(f"{filepath}: Found match")
                except Exception:
                    pass

        if found:
            print("Found relevant context:")
            print("\n".join(found[:20])) # show top 20
        else:
            print("No immediate local context found.")
    except Exception as e:
        print(f"Research failed: {e}")
    print("Research complete.")

def run_test(command: str):
    print(f"--- TESTING AGENT ---")
    print(f"Running automated test suite: {command}")
    try:
        result = subprocess.run(command.split(), capture_output=True, text=True, timeout=10)
        print("Test Output:")
        print(result.stdout)
        if result.returncode != 0:
            print("Test Errors:")
            print(result.stderr)
            sys.exit(1)
        else:
            print("Tests passed successfully.")
    except Exception as e:
        print(f"Test runner failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parallel Worker Agent for Sonu CLI")
    parser.add_argument("role", choices=["research", "test"], help="Role of the sub-agent")
    parser.add_argument("payload", help="The query or command payload")

    args = parser.parse_args()

    if args.role == "research":
        run_research(args.payload)
    elif args.role == "test":
        run_test(args.payload)
