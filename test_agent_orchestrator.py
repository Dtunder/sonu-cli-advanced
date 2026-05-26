import unittest
import asyncio
from agent_orchestrator import LocalCloudOrchestrator

class TestLocalCloudOrchestrator(unittest.TestCase):
    def test_execute_parallel(self):
        orchestrator = LocalCloudOrchestrator()

        # We need a small python script to test.
        tasks = {
            "test_print": ["python", "-c", "print('hello world')"],
            "test_err": ["python", "-c", "import sys; sys.stderr.write('error msg'); sys.exit(1)"]
        }

        results = asyncio.run(orchestrator.execute_parallel(tasks))

        self.assertIn("test_print", results)
        self.assertIn("test_err", results)

        self.assertEqual(results["test_print"]["returncode"], 0)
        self.assertEqual(results["test_print"]["stdout"].strip(), "hello world")
        self.assertEqual(results["test_print"]["stderr"].strip(), "")

        self.assertEqual(results["test_err"]["returncode"], 1)
        self.assertEqual(results["test_err"]["stdout"].strip(), "")
        self.assertEqual(results["test_err"]["stderr"].strip(), "error msg")

if __name__ == '__main__':
    unittest.main()
