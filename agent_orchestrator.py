import asyncio
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class LocalCloudOrchestrator:
    """
    Spawns parallel local Python subprocesses to execute diagnostics,
    run tests, or search directories concurrently, and aggregates their
    results asynchronously.
    """

    def __init__(self):
        pass

    async def _run_task(self, name: str, command: List[str]) -> Dict[str, Any]:
        """
        Executes a single command asynchronously as a subprocess.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return {
                "name": name,
                "command": command,
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            logger.error(f"Error executing task {name}: {e}")
            return {
                "name": name,
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    async def execute_parallel(
        self, tasks: Dict[str, List[str]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Executes multiple tasks concurrently and aggregates their results.

        Args:
            tasks: A dictionary mapping task names to commands (list of strings).

        Returns:
            A dictionary mapping task names to their result dictionaries containing
            returncode, stdout, and stderr.
        """
        coroutines = [self._run_task(name, cmd) for name, cmd in tasks.items()]
        results_list = await asyncio.gather(*coroutines)

        aggregated_results = {}
        for result in results_list:
            aggregated_results[result["name"]] = result

        return aggregated_results
