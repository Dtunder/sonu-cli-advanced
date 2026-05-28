import os
from collections import deque

class PredictiveDebugger:
    """
    Analyzes log files to predict potential cascading failures by detecting
    high-frequency error patterns.
    """
    def __init__(self, log_path: str):
        """
        Initializes the PredictiveDebugger.

        Args:
            log_path: The full path to the log file to be monitored.
        """
        self.log_path = log_path
        self.error_keywords = ['traceback', 'error', 'exception']
        self.window_size = 20
        self.threshold = 3
        self.scan_lines = 100

    def analyze(self) -> list[str]:
        """
        Reads the last N lines of the log file and analyzes them for error clusters.

        Returns:
            A list of warning strings if error frequency exceeds the threshold
            in any sliding window. Returns an empty list if no issues are found
            or the log file doesn't exist.
        """
        if not os.path.exists(self.log_path):
            return [f"Log file not found at: {self.log_path}"]

        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
                # Read last N lines efficiently
                last_lines = deque(f, self.scan_lines)
        except Exception as e:
            return [f"Error reading log file: {e}"]

        warnings = []

        # Not enough lines to analyze
        if len(last_lines) < self.window_size:
            return []

        # Sliding window analysis
        for i in range(len(last_lines) - self.window_size + 1):
            window = [line.lower() for line in list(last_lines)[i:i+self.window_size]]

            error_count = 0
            for line in window:
                if any(keyword in line for keyword in self.error_keywords):
                    error_count += 1

            if error_count > self.threshold:
                warning_message = (
                    f"Predictive Warning: Found {error_count} errors/exceptions "
                    f"within a {self.window_size}-line window (threshold is >{self.threshold}). "
                    f"Potential instability detected."
                )
                if warning_message not in warnings:
                    warnings.append(warning_message)

        return warnings
