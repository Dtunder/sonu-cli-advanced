
import re
from sonu_client import SonuClient

def test_scrubbing():
    client = SonuClient()

    test_cases = [
        ("Shubham Jayswal is the owner.", "Lead Systems Architect is the owner."),
        ("Hello Shubham.", "Hello Developer."),
        ("Mr. Jayswal is here.", "Mr. Architect is here."),
        ("Path: C:\\Users\\user\\sonu-cli-advanced\\main.py", "Path: C:\\Users\\developer\\workspace\\main.py"),
        ("Other Path: C:\\Users\\someone\\Documents", "Other Path: C:\\Users\\developer\\Documents"),
        ("OS: Windows", "OS: Windows"),
        ("Shell: PowerShell", "Shell: PowerShell"),
        (None, ""),
    ]

    for input_text, expected_output in test_cases:
        actual_output = client._scrub_sensitive_data(input_text)
        print(f"Input: {input_text}")
        print(f"Expected: {expected_output}")
        print(f"Actual:   {actual_output}")
        assert actual_output == expected_output
        print("MATCH!")
        print("-" * 20)

if __name__ == "__main__":
    test_scrubbing()
