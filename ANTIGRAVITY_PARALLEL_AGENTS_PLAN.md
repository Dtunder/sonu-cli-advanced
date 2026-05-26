# Antigravity-Style Parallel Agent Architecture for Sonu CLI

## 1. Core Methodology (The "Antigravity" Paradigm)
Die Methodik von Tools wie "Antigravity CLI" basiert auf extremer Autonomie, massiver Parallelisierung und fehlertoleranter Selbstkorrektur. Anstatt darauf zu warten, dass der Nutzer Befehle eingibt, agiert das System im Hintergrund als fortwährender Orchestrator.

**Prinzipien:**
1. **Parallel Tree-Search Execution:** Aufgaben werden in Sub-Tasks zerlegt, und an mehrere isolierte Worker-Agenten parallel vergeben.
2. **Environment Sandboxing:** Jeder parallele Agent testet seinen Lösungsansatz in einem eigenen virtuellen Workspace oder Docker-Container.
3. **Automated Verification Loop:** Ein Agent gilt erst als "fertig", wenn die bereitgestellten (oder selbst geschriebenen) Tests grün sind.
4. **Asynchronous Background Operation:** Der Main-Agent (Orchestrator) blockiert niemals. Er sammelt Ergebnisse ein und führt Merge-Konflikte zusammen.

## 2. Architektur für Sonu CLI

Um diese Methodik nativ in Sonu CLI zu integrieren, erweitern wir das System um einen **Parallel Agent Orchestrator**.

### A. The Orchestrator (`agent_orchestrator.py`)
- Nimmt einen komplexen Goal-State (z.B. `/auto migrate to typescript`) entgegen.
- **Decomposition Engine:** Ein spezieller LLM-Call zerlegt das Goal in einen DAG (Directed Acyclic Graph) von unabhängigen Tasks.
- Startet asynchrone Background-Threads (via `ProcessManager`), die jeweils einen isolierten Subagenten (instanziiert als `OpenAICompatibleAgent` oder nativen `Gemini Client`) beinhalten.

### B. Parallel Worker Agents (`worker_agent.py`)
- Jeder Worker hat Zugriff auf einen **isolierten Git-Branch** oder ein temporäres Verzeichnis.
- **Tools:** Voller Lese-/Schreibzugriff + Ausführen von Bash-Skripten.
- **Verification Loop:** Bevor der Agent seinen Code zurückgibt, muss er das Kommando `pytest` oder `npm test` ausführen. Schlägt es fehl, repariert er den Code selbstständig (bis zu einem Max-Retry-Limit).

### C. Merge & Consensus (`debate_engine.py` Upgrade)
- Wenn parallele Agenten unterschiedliche Dateien bearbeiten, führt der Orchestrator einen Git Merge durch.
- Bei Konflikten (Merge Conflicts) wird die `SwarmConsensusServer` Logik genutzt: Agent-Architect und Agent-Critic debattieren und lösen den Konflikt kryptographisch signiert.

## 3. Implementierungsplan (Roadmap)

### Phase 1: Branch-Level Sandboxing
- Implementiere ein Tool `create_sandbox_branch(task_id)`, das für jeden Subagenten einen eigenen Git-Worktree oder Branch anlegt.
- Update des `SonuClient`, um Kontext auf diesen Branch zu beschränken.

### Phase 2: Asynchroner DAG-Scheduler
- Erweitere `ProcessManager`, um LLM-Aufgaben (nicht nur Shell-Befehle) in den Hintergrund zu schieben.
- Implementiere `wait_for_tasks([task1, task2])` um auf parallele Agenten zu warten.

### Phase 3: Der Verification Loop
- Erzwinge im Prompt: "Do not return a success signal until you have run `pytest <file>` and received exit code 0."
- Falls der Subagent aufgibt, meldet er sich beim Orchestrator, der einen anderen Agenten mit einer neuen Strategie spawnt.

### Phase 4: CLI Interface (`main.py`)
- Neuer Befehl: `/swarm <prompt>`
- Beispiel: `/swarm Refactor database module to use SQLAlchemy and add 100% test coverage`.
- UI zeigt ein dynamisches Tree-View-Dashboard (via `rich` library), das live anzeigt, welcher Agent gerade schreibt, testet oder debuggt.
