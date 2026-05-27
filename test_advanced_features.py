import os
import sys
import time

def test_memory_manager():
    print("[TEST] Teste MemoryManager...")
    from memory_manager import MemoryManager
    
    # MM initialisieren
    mm = MemoryManager()
    
    # 4-Level Gedaechtnis abrufen
    context = mm.load_memory(os.getcwd())
    
    assert "GLOBAL MEMORY" in context, "Globales Gedaechtnis fehlt!"
    assert "PRIVATE MACHINE MEMORY" in context, "Maschinenspezifisches Gedaechtnis fehlt!"
    assert "PROJECT MEMORY" in context, "Projektweites Gedaechtnis fehlt!"
    
    print("[SUCCESS] MemoryManager erfolgreich getestet!\n")


def test_skills_manager():
    print("[TEST] Teste SkillsManager...")
    from skills_manager import SkillsManager
    
    sm = SkillsManager()
    skills = sm.list_skills()
    
    print(f"Gefundene Skills: {skills}")
    assert "cybernetic-thinking" in skills, "cybernetic-thinking Skill fehlt!"
    assert "system-architect" in skills, "system-architect Skill fehlt!"
    
    # Skill aktivieren
    content = sm.activate_skill("cybernetic-thinking")
    assert sm.active_skill == "cybernetic-thinking"
    assert "mechatronischen Denkrahmen" in content, "Skill-Inhalt ist inkorrekt!"
    
    # Skill deaktivieren
    sm.deactivate_skill()
    assert sm.active_skill is None
    
    print("[SUCCESS] SkillsManager erfolgreich getestet!\n")


def test_process_manager():
    print("[TEST] Teste ProcessManager...")
    from process_manager import ProcessManager
    
    pm = ProcessManager()
    
    # Hintergrundbefehl starten (kurzer Ping)
    if os.name == 'nt':
        cmd = "ping 127.0.0.1 -n 3"
    else:
        cmd = "ping -c 3 127.0.0.1"
    print(f"Starte Hintergrundprozess: {cmd}")
    tid = pm.start_task(cmd)
    
    print(f"Task gestartet mit ID: {tid}")
    assert tid > 0, "Ungueltige Task-ID!"
    
    # Warte kurz und poll Status
    time.sleep(1.5)
    tasks = pm.list_tasks()
    found = False
    for t in tasks:
        if t["id"] == tid:
            found = True
            print(f"Status von Task {tid}: {t['status']}")
            
    assert found, "Task nicht in Taskliste gefunden!"
    
    # Logs lesen
    time.sleep(1.5)
    logs = pm.read_task_output(tid)
    # Emojis/Unicode sicher fuer Windows Terminal konvertieren
    safe_logs = logs.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
    print(f"Logs von Task {tid}:\n{safe_logs}")
    assert len(logs) > 0, "Keine Logs erzeugt!"
    
    # Task killen (falls noch aktiv)
    pm.kill_task(tid)
    print("[SUCCESS] ProcessManager erfolgreich getestet!\n")


if __name__ == "__main__":
    print("=== STARTE AUTOMATISIERTE VALIDIERUNG DER ADVANCED-ARCHITEKTUR ===\n")
    try:
        test_memory_manager()
        test_skills_manager()
        test_process_manager()
        print("=== ALLE TESTS ERFOLGREICH BESTANDEN! ===")
        sys.exit(0)
    except AssertionError as e:
        print(f"[FAIL] Zusicherung fehlgeschlagen: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unerwarteter Fehler: {e}")
        sys.exit(1)
