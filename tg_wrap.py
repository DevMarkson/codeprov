#!/usr/bin/env python3
"""
Terminal Interactive Process Wrapper with Telegram Approval for Windows
Uses threaded non-blocking I/O to seamlessly intercept prompts and inject user choices.
"""

import sys
import os
import subprocess
import threading
import queue
import re
import time
import asyncio
from pathlib import Path
import httpx

# Load .env configuration
def load_env():
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v

load_env()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8854518763:AAHWkJnErvbfPwpahIuN6P41fXop0WLjbuI")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6223910867")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

PROMPT_PATTERNS = [
    re.compile(r"\[y/n\]", re.IGNORECASE),
    re.compile(r"\(y/n\)", re.IGNORECASE),
    re.compile(r"\[yes/no\]", re.IGNORECASE),
    re.compile(r"\(yes/no\)", re.IGNORECASE),
    re.compile(r"do you want to continue\?", re.IGNORECASE),
    re.compile(r"are you sure\?", re.IGNORECASE),
    re.compile(r"proceed\?", re.IGNORECASE),
]

async def request_mobile_approval(snippet: str) -> str:
    keyboard = {
        "inline_keyboard": [
            [{"text": "✅ 1. Yes (Proceed)", "callback_data": "yes"}],
            [{"text": "⚙️ 2. Yes, with settings", "callback_data": "yes_settings"}],
            [{"text": "⏭️ 3. Skip", "callback_data": "skip"}, {"text": "❌ 4. No (Abort)", "callback_data": "no"}]
        ]
    }

    msg_text = f"🔔 *Terminal Approval Request*\n\n```text\n{snippet.strip()}\n```\n_Tap an option or send custom input:_"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Flush older updates
        updates_res = await client.get(f"{API_BASE}/getUpdates?offset=-1")
        last_update_id = 0
        if updates_res.status_code == 200:
            updates = updates_res.json().get("result", [])
            if updates:
                last_update_id = updates[-1]["update_id"]

        # Send approval prompt
        send_res = await client.post(
            f"{API_BASE}/sendMessage",
            json={
                "chat_id": int(CHAT_ID),
                "text": msg_text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }
        )
        msg_data = send_res.json()
        sent_msg_id = msg_data.get("result", {}).get("message_id")

        print(f"\n[Telegram Bridge] Intercepted prompt! Forwarded to @codeprovBot. Waiting for phone...")

        while True:
            try:
                res = await client.get(f"{API_BASE}/getUpdates?offset={last_update_id + 1}&timeout=10")
                if res.status_code != 200:
                    await asyncio.sleep(1)
                    continue

                items = res.json().get("result", [])
                for item in items:
                    last_update_id = item["update_id"]

                    if "callback_query" in item:
                        cq = item["callback_query"]
                        if str(cq["from"]["id"]) == str(CHAT_ID):
                            choice = cq["data"]
                            await client.post(f"{API_BASE}/answerCallbackQuery", json={"callback_query_id": cq["id"]})
                            labels = {
                                "yes": "✅ 1. Yes (Proceed)",
                                "yes_settings": "⚙️ 2. Yes, with settings",
                                "skip": "⏭️ 3. Skip",
                                "no": "❌ 4. No (Abort)"
                            }
                            selected_label = labels.get(choice, choice)
                            if sent_msg_id:
                                await client.post(
                                    f"{API_BASE}/editMessageText",
                                    json={
                                        "chat_id": int(CHAT_ID),
                                        "message_id": sent_msg_id,
                                        "text": f"{msg_text}\n\n*Selected on Phone:* `{selected_label}`",
                                        "parse_mode": "Markdown"
                                    }
                                )
                            if choice == "yes":
                                return "y"
                            elif choice == "no":
                                return "n"
                            elif choice == "yes_settings":
                                return "2"
                            elif choice == "skip":
                                return ""
                            else:
                                return choice

                    if "message" in item and "text" in item["message"]:
                        msg = item["message"]
                        if str(msg["from"]["id"]) == str(CHAT_ID):
                            text = msg["text"]
                            await client.post(
                                f"{API_BASE}/sendMessage",
                                json={
                                    "chat_id": int(CHAT_ID),
                                    "text": f"✅ *Injected into Terminal:* `{text}`",
                                    "parse_mode": "Markdown"
                                }
                            )
                            return text

            except Exception:
                await asyncio.sleep(1)

def run_wrapped_command(cmd_args):
    # Ensure unbuffered python execution if child is python
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        cmd_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        env=env
    )

    buffer = ""
    lock = threading.Lock()
    prompt_active = False

    def reader_thread():
        nonlocal buffer, prompt_active
        while proc.poll() is None:
            char_bytes = proc.stdout.read(1)
            if not char_bytes:
                break
            try:
                char = char_bytes.decode('utf-8', errors='ignore')
            except Exception:
                continue
            
            sys.stdout.write(char)
            sys.stdout.flush()

            with lock:
                buffer += char
                if len(buffer) > 200:
                    buffer = buffer[-200:]
                
                # Check for prompt
                if not prompt_active:
                    for pattern in PROMPT_PATTERNS:
                        if pattern.search(buffer):
                            prompt_active = True
                            # Ask mobile
                            snippet = buffer[-100:]
                            decision = asyncio.run(request_mobile_approval(snippet))
                            print(f"\n[Telegram Bridge] Injecting '{decision}' into process...")
                            try:
                                proc.stdin.write((decision + "\n").encode('utf-8'))
                                proc.stdin.flush()
                            except (BrokenPipeError, OSError):
                                pass
                            buffer = ""
                            prompt_active = False
                            break

    t = threading.Thread(target=reader_thread, daemon=True)
    t.start()
    proc.wait()
    t.join(timeout=2)
    return proc.returncode

def main():
    if len(sys.argv) < 2:
        print("Usage: python tg_wrap.py <command_to_run> [args...]")
        print("Example: python tg_wrap.py python test_prompt.py")
        sys.exit(1)

    cmd = sys.argv[1:]
    exit_code = run_wrapped_command(cmd)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
