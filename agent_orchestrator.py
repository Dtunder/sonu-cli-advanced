import asyncio
import uuid
import json
import os
import subprocess
import logging
from typing import List, Dict, Any

logger = logging.getLogger("LocalCloudOrchestrator")

class SubAgentTask:
    def __init__(self, name: str, instruction: str, task_type: str = "subprocess"):
        self.id = str(uuid.uuid4())
        self.name = name
        self.instruction = instruction
        self.task_type = task_type
        self.status = "pending"
        self.result = None

class LocalCloudOrchestrator:
    """
    Spawns and manages parallel sub-agents (as local subprocesses or async calls).
    This allows Sonu to offload heavy diagnostic, testing, or code-writing tasks
    to independent worker agents running concurrently.
    """
    def __init__(self, ui):
        self.ui = ui
        self.tasks: Dict[str, SubAgentTask] = {}
        self.running_processes = {}
        self.loop = asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else asyncio.new_event_loop()

    def dispatch_subprocess_agent(self, name: str, script_path: str, args: List[str]) -> str:
        """Spawnt einen Hintergrund-Python-Prozess für isolierte Ausführung."""
        task = SubAgentTask(name, f"Execute {script_path}", task_type="subprocess")
        self.tasks[task.id] = task
        self.ui.show_info(f"[Orchestrator] Spawning Sub-Agent '{name}' (Task: {task.id})")

        import sys
        cmd = [sys.executable, script_path] + args
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.running_processes[task.id] = proc
        task.status = "running"
        return task.id

    async def _async_wait_task(self, task_id: str):
        """Asynchrones Warten auf einen Subprozess."""
        proc = self.running_processes.get(task_id)
        if not proc:
            return None

        stdout, stderr = await asyncio.to_thread(proc.communicate)
        task = self.tasks[task_id]

        if proc.returncode == 0:
            task.status = "success"
            task.result = stdout
        else:
            task.status = "failed"
            task.result = stderr

        return task

    async def wait_for_all(self):
        """Wartet auf alle laufenden Sub-Agenten und sammelt die Ergebnisse."""
        self.ui.show_spinner("Warte auf parallele Sub-Agenten...")
        running_task_ids = [tid for tid, t in self.tasks.items() if t.status == "running"]

        results = await asyncio.gather(*(self._async_wait_task(tid) for tid in running_task_ids))

        aggregated = {}
        for task in results:
            if task:
                self.ui.show_info(f"[Orchestrator] Sub-Agent '{task.name}' beendet. Status: {task.status}")
                aggregated[task.name] = {
                    "status": task.status,
                    "result": task.result[:500] + ("..." if len(task.result) > 500 else "")
                }
        return aggregated

    def dispatch_research_agent(self, query: str) -> str:
        """Delegates a heavy research task to a specialized agent."""
        # Instead of a full subprocess, we could use the MultiProviderClient natively
        # but the prompt specifically asked for subprocesses or distinct agents.
        # We will create a worker script to run the research agent.
        worker_script = os.path.join(os.path.dirname(__file__), "worker_agent.py")
        return self.dispatch_subprocess_agent("ResearchAgent", worker_script, ["research", query])

    def dispatch_testing_agent(self, test_command: str) -> str:
        """Delegates the task of running tests and reporting."""
        worker_script = os.path.join(os.path.dirname(__file__), "worker_agent.py")
        return self.dispatch_subprocess_agent("TestingAgent", worker_script, ["test", test_command])
