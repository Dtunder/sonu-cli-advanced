#!/usr/bin/env python3
"""
jules_delegator.py
Headless task-delegation wrapper for Google Jules autonomous coding agent.

Usage:
    python jules_delegator.py "Your task description here"
    python jules_delegator.py "Your task" --manual          # pause before approving plan
    python jules_delegator.py --session 123456789012345678  # resume / monitor existing session
    python jules_delegator.py "Your task" --log-level DEBUG
"""

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_KEY_PATH = Path(r"C:\Users\user\.gemini\antigravity-ide\scratch\jules_api_key.txt")
JULES_API_BASE = "https://jules.googleapis.com/v1alpha"

POLL_INTERVAL_SECONDS = 30
MAX_BACKOFF_SECONDS = 300
MAX_POLL_ATTEMPTS = 240  # 2 hours at 30 s intervals before giving up

# Normalised (lower-case) status strings Jules reports
STATUS_AWAITING_APPROVAL = "awaiting plan approval"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_TERMINAL = {STATUS_COMPLETED, STATUS_FAILED, "error", "cancelled"}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("jules_delegator")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_api_key() -> str:
    if not API_KEY_PATH.exists():
        log.error("API key file not found: %s", API_KEY_PATH)
        sys.exit(1)
    key = API_KEY_PATH.read_text(encoding="utf-8").strip()
    if not key:
        log.error("API key file is empty: %s", API_KEY_PATH)
        sys.exit(1)
    return key


def run_cmd(cmd: str, stream_output: bool = False) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=not stream_output,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def extract_session_id(text: str) -> str | None:
    """Pull an 18-20 digit session ID from arbitrary text."""
    match = re.search(r"\b(\d{18,20})\b", text)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Jules CLI interactions
# ---------------------------------------------------------------------------

def spawn_session(prompt: str, api_key: str) -> str:
    """Start a new Jules session via REST API and return its session ID."""
    log.info("Spawning Jules session via REST API for prompt: %s", prompt[:80])
    
    url = f"{JULES_API_BASE}/sessions"
    payload = json.dumps({
        "prompt": prompt,
        "sourceContext": {
            "source": "sources/github/Dtunder/nasuta-evo8",
            "githubRepoContext": {
                "startingBranch": "evo9-bugfix-base"
            }
        },
        "requirePlanApproval": True
    }).encode("utf-8")
    
    headers = {
        "X-Goog-Api-Key": api_key,
        "Content-Type": "application/json",
    }
    
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            # Name format: "sessions/123456789012345678"
            session_name = data.get("name", "")
            session_id = session_name.split("/")[-1]
            if not session_id:
                log.error("Could not parse session ID from response: %s", body)
                sys.exit(1)
            log.info("Session spawned  id=%s", session_id)
            return session_id
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        log.error("HTTP %d spawning session: %s", exc.code, body)
        sys.exit(1)
    except Exception as exc:
        log.error("Error spawning session: %s", exc)
        sys.exit(1)


def get_session_status(session_id: str) -> str:
    """
    Return the current status for *session_id* as a lower-case string.

    Splits each data line on whitespace and collects tokens that follow the
    session ID up to the first date-shaped token (YYYY-MM-DD), which handles
    multi-word statuses like "In Progress" or "Awaiting Plan Approval" without
    relying on fragile fixed column offsets.
    """
    rc, stdout, stderr = run_cmd("jules remote list --session")
    if rc != 0:
        log.warning("jules remote list exited %d; treating status as unknown.\n%s", rc, stderr.strip())
        return "unknown"

    for line in (stdout + "\n" + stderr).splitlines():
        if session_id not in line:
            continue
        parts = line.split()
        try:
            sid_idx = next(i for i, p in enumerate(parts) if session_id in p)
        except StopIteration:
            continue
        status_words: list[str] = []
        for token in parts[sid_idx + 1:]:
            if re.match(r"\d{4}-\d{2}-\d{2}", token):
                break
            status_words.append(token)
        status = " ".join(status_words).lower().strip()
        # Normalise truncated variants like "awaiting plan a…"
        if "awaiting plan" in status:
            return "awaiting plan approval"
        return status or "unknown"

    log.debug("Session %s not found in list output; still initialising.", session_id)
    return "initialising"


# ---------------------------------------------------------------------------
# REST API — plan approval with exponential backoff
# ---------------------------------------------------------------------------

def approve_plan(session_id: str, api_key: str) -> bool:
    """
    POST an approval message to the Jules REST endpoint.
    Retries iteratively with exponential backoff on 429 / 5xx / network errors.
    """
    url = f"{JULES_API_BASE}/sessions/{session_id}:sendMessage"
    payload = json.dumps(
        {"prompt": "Plan approved. Please proceed with the implementation."}
    ).encode("utf-8")
    headers = {
        "X-Goog-Api-Key": api_key,
        "Content-Type": "application/json",
    }

    for attempt in range(10):  # up to ~85 minutes of cumulative backoff
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                log.info("Plan approval sent (HTTP %d): %s", resp.status, body[:120])
                return True

        except urllib.error.HTTPError as exc:
            if exc.code == 429 or exc.code >= 500:
                backoff = min(2 ** attempt * 5, MAX_BACKOFF_SECONDS)
                log.warning("HTTP %d – retrying approval in %ds…", exc.code, backoff)
                time.sleep(backoff)
                continue
            body = exc.read().decode("utf-8", errors="replace")
            log.error("HTTP %d approving plan: %s", exc.code, body[:300])
            return False

        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            backoff = min(2 ** attempt * 5, MAX_BACKOFF_SECONDS)
            log.warning("Network error (%s) – retrying in %ds…", exc, backoff)
            time.sleep(backoff)

    log.error("Approval failed after 10 attempts.")
    return False


# ---------------------------------------------------------------------------
# Patch application
# ---------------------------------------------------------------------------

def pull_and_apply(session_id: str) -> bool:
    """Run jules remote pull --session <id> --apply, streaming output live."""
    log.info("Pulling and applying patch for session %s…", session_id)
    cmd = f"jules remote pull --session {session_id} --apply"
    rc, _, _ = run_cmd(cmd, stream_output=True)
    if rc == 0:
        log.info("Patch applied successfully.")
        return True
    log.error("jules remote pull exited with code %d.", rc)
    return False


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------

def run_delegation(session_id: str, api_key: str, manual_approve: bool = False) -> None:
    plan_approved = False
    last_status = ""

    for attempt in range(MAX_POLL_ATTEMPTS):
        status = get_session_status(session_id)

        if status != last_status:
            log.info("[%s]  Status → %s", session_id, status.title())
            last_status = status

        # --- Plan approval gate ------------------------------------------
        if status == STATUS_AWAITING_APPROVAL and not plan_approved:
            if manual_approve:
                input("  [manual mode] Press Enter to approve the plan and continue… ")
            else:
                log.info("Auto-approving plan…")

            if approve_plan(session_id, api_key):
                plan_approved = True
            else:
                log.warning("Approval failed; will retry next poll cycle.")

        # --- Terminal states ---------------------------------------------
        elif status == STATUS_COMPLETED:
            log.info("Session completed – applying patch…")
            ok = pull_and_apply(session_id)
            sys.exit(0 if ok else 1)

        elif status in STATUS_TERMINAL:
            log.error("Session ended with terminal status '%s'. Exiting.", status)
            sys.exit(1)

        # --- Sleep before next poll (shorter back-off while initialising) --
        if status == "initialising" and attempt < 4:
            sleep_secs = min(POLL_INTERVAL_SECONDS, 2 ** attempt * 3 + 5)
        else:
            sleep_secs = POLL_INTERVAL_SECONDS

        log.debug("Next poll in %ds…", sleep_secs)
        time.sleep(sleep_secs)

    log.error("Reached %d poll attempts without completion. Giving up.", MAX_POLL_ATTEMPTS)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Headless Jules task-delegation wrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("prompt", nargs="?", metavar="PROMPT",
                        help="Task description to send to Jules (spawns a new session)")
    source.add_argument("--session", "-s", metavar="SESSION_ID",
                        help="Resume / monitor an existing session instead of spawning a new one")

    parser.add_argument("--manual", action="store_true",
                        help="Pause and wait for keyboard confirmation before approving the plan")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging verbosity (default: INFO)")
    args = parser.parse_args()

    # argparse doesn't enforce required=True on a group that contains a
    # nargs="?" positional — both can be None if the user supplies no arguments.
    if not args.session and not args.prompt:
        parser.error("Provide a PROMPT or use --session SESSION_ID.")

    logging.getLogger().setLevel(args.log_level)
    api_key = read_api_key()

    if args.session:
        session_id = args.session.strip()
        if not re.fullmatch(r"\d{18,20}", session_id):
            log.error("'%s' does not look like a valid Jules session ID (18-20 digits).", session_id)
            sys.exit(1)
        log.info("Resuming session %s", session_id)
    else:
        session_id = spawn_session(args.prompt, api_key)

    run_delegation(session_id, api_key, manual_approve=args.manual)


if __name__ == "__main__":
    main()
