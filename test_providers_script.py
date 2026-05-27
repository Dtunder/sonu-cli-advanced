import os
import sys
from dotenv import load_dotenv

# Terminal encoding for Windows
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sonu_client import SonuClient
from terminal_ui import TerminalUI

class MockUI(TerminalUI):
    def show_welcome(self): pass
    def show_spinner(self, message=""):
        class DummySpinner:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb): pass
        return DummySpinner()
    def show_info(self, info_message):
        # Console-safe print
        safe_msg = info_message.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        print(f"[INFO] {safe_msg}")
    def show_error(self, error_message):
        safe_msg = error_message.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        print(f"[ERROR] {safe_msg}")
    def display_response(self, text):
        safe_msg = text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        print(f"[RESPONSE] {safe_msg}")

def run_test_provider(client, ui, name):
    print(f"\n==========================================")
    print(f"TESTE PROVIDER: {name}")
    print(f"==========================================")
    
    ok, msg = client.set_provider(name)
    if not ok:
        print(f"[FAIL] Wechseln zu {name} fehlgeschlagen: {msg}")
        return False
        
    print(f"[OK] {msg}")
    print(f"Aktives Modell: {client.model_name}")
    
    try:
        print(f"Sende Testabfrage an {name}...")
        resp = client.run_agent_turn("Wer bist du? Antworte in genau einem kurzen Satz auf Deutsch.", ui)
        print(f"[SUCCESS] Antwort von {name}:")
        ui.display_response(resp)
        return True
    except Exception as e:
        print(f"[FAIL] Fehler bei {name}: {e}")
        return False

def main():
    load_dotenv(override=True)
    ui = MockUI()
    
    try:
        client = SonuClient()
    except Exception as e:
        print(f"Fehler bei Initialisierung: {e}")
        sys.exit(1)
        
    results = {}
    
    # Teste Groq
    if os.getenv("GROQ_API_KEY"):
        results["groq"] = run_test_provider(client, ui, "groq")
    else:
        print("GROQ_API_KEY fehlt in .env, ueberspringe.")
        
    # Teste xAI (Grok)
    if os.getenv("XAI_API_KEY"):
        results["xai"] = run_test_provider(client, ui, "xai")
    else:
        print("XAI_API_KEY fehlt in .env, ueberspringe.")
        
    # Teste OpenRouter
    if os.getenv("OPENROUTER_API_KEY"):
        results["openrouter"] = run_test_provider(client, ui, "openrouter")
    else:
        print("OPENROUTER_API_KEY fehlt in .env, ueberspringe.")
        
    # Teste Hugging Face
    if os.getenv("HF_TOKEN"):
        results["huggingface"] = run_test_provider(client, ui, "huggingface")
    else:
        print("HF_TOKEN fehlt in .env, ueberspringe.")

    print("\n==========================================")
    print("TEST-ERGEBNISSE:")
    print("==========================================")
    all_ok = True
    for prov, success in results.items():
        status = "PASSED" if success else "FAILED"
        print(f"  • {prov.upper()}: {status}")
        if not success:
            all_ok = False
            
    if all_ok:
        print("\n=== ALLE PROVIDER HABEN ERFOLGREICH GEANTWORTET! ===")
        sys.exit(0)
    else:
        print("\n=== EINIGE PROVIDER-TESTS SIND FEHLGESCHLAGEN. ===")
        sys.exit(1)

if __name__ == "__main__":
    main()
