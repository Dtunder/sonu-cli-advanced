import asyncio
import logging
from typing import Protocol, Any, Dict

# Configure structured logging for performance systems
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimulationInterface(Protocol):
    """Protocol for the Oekolopoly Reinforcement Learning simulation."""
    async def start(self, output_queue: asyncio.Queue) -> None: ...
    def stop(self) -> None: ...

class ExecutionInterface(Protocol):
    """Protocol for the High-Frequency Trading execution engine."""
    async def start(self, input_queue: asyncio.Queue) -> None: ...
    def stop(self) -> None: ...

class PipelineManager:
    """
    Central entry point orchestrating data flow between the Oekolopoly RL Simulation
    and the HFT Execution Engine.

    Designed with asyncio for high-throughput, low-latency concurrent processing
    with backpressure handling.
    """
    def __init__(self, simulation: SimulationInterface, execution_engine: ExecutionInterface, queue_maxsize: int = 10000):
        # Bounded queue to ensure memory stability if execution lags simulation
        self.signal_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_maxsize)
        self.simulation = simulation
        self.execution_engine = execution_engine
        self._tasks: list[asyncio.Task] = []

    async def run(self) -> None:
        """Starts the pipeline and manages the lifecycle of components."""
        logger.info("Initializing HFT Pipeline Manager...")

        # Spawn concurrent tasks
        sim_task = asyncio.create_task(self.simulation.start(self.signal_queue), name="SimulationTask")
        exec_task = asyncio.create_task(self.execution_engine.start(self.signal_queue), name="ExecutionTask")

        self._tasks = [sim_task, exec_task]

        try:
            logger.info("Pipeline components running.")
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("Pipeline Manager received cancellation signal.")
            await self.shutdown()
        except Exception as e:
            logger.error(f"Critical error in pipeline: {e}", exc_info=True)
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shuts down the pipeline and its components."""
        logger.info("Initiating graceful shutdown...")

        # Stop components from producing/consuming
        self.simulation.stop()
        self.execution_engine.stop()

        # Cancel running tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Await task cancellation
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Shutdown complete.")

# -----------------------------------------------------------------------------
# Default mock implementations for testing and standalone execution
# -----------------------------------------------------------------------------

class MockOekolopolySimulation:
    def __init__(self):
        self.running = False

    async def start(self, output_queue: asyncio.Queue) -> None:
        self.running = True
        logger.info("[Mock] Oekolopoly Simulation started.")
        try:
            while self.running:
                await asyncio.sleep(0.01) # Simulate high-frequency tick
                signal = {"asset": "OEK", "action": "BUY", "confidence": 0.99}
                try:
                    # Using put_nowait to avoid blocking the simulation loop if queue is full
                    output_queue.put_nowait(signal)
                except asyncio.QueueFull:
                    logger.warning("[Mock] Signal queue full, dropping signal. Check execution engine latency.")
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            logger.info("[Mock] Oekolopoly Simulation stopped.")

    def stop(self) -> None:
        self.running = False

class MockHFTExecutionEngine:
    def __init__(self):
        self.running = False

    async def start(self, input_queue: asyncio.Queue) -> None:
        self.running = True
        logger.info("[Mock] HFT Execution Engine started.")
        try:
            while self.running:
                signal = await input_queue.get()
                # Simulate ultra-low latency execution here
                input_queue.task_done()
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            logger.info("[Mock] HFT Execution Engine stopped.")

    def stop(self) -> None:
        self.running = False

if __name__ == "__main__":
    # Example standalone usage
    sim = MockOekolopolySimulation()
    exec_engine = MockHFTExecutionEngine()
    manager = PipelineManager(sim, exec_engine)

    try:
        # Run event loop
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
