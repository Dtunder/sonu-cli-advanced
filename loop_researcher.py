import subprocess
import time
import os
import shutil

def run_background_research():
    # Definiere den Pfad und den Command
    script_path = "batch_researcher.py"
    cmd = f"python {script_path}"
    
    # Endlosschleife mit 30 Minuten Intervall
    while True:
        try:
            print(f"[{time.ctime()}] Starte Research-Agent...")
            # Start als Hintergrundprozess
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                print(f"Error in Research-Agent: {stderr.decode()}")
            else:
                print(f"Research-Agent erfolgreich beendet.")
                
        except Exception as e:
            print(f"Kritischer Fehler im Loop: {e}")
            
        print("Warte 30 Minuten bis zum nächsten Durchlauf...")
        time.sleep(1800)

if __name__ == "__main__":
    run_background_research()
