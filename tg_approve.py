#!/usr/bin/env python3
"""
Telegram Remote Approval Bridge for Antigravity & Terminal Prompts
Supports standard 4 options:
 1. Yes (Proceed)
 2. Yes, with settings / modify
 3. Skip / Next
 4. No (Abort)
Plus direct free-text response from Telegram.
"""

import sys
import asyncio
import os
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Automatically load .env if present
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

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

class TelegramApprovalBridge:
    def __init__(self, bot_token: str, chat_id: str):
        if not bot_token or not chat_id:
            raise ValueError(
                "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. "
                "Please configure them in .env or as environment variables."
            )
        self.bot_token = bot_token
        self.chat_id = int(chat_id)
        self.response_event = None
        self.user_response = None

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        self.user_response = query.data
        labels = {
            "yes": "✅ Yes (Proceed)",
            "yes_settings": "⚙️ Yes, with settings",
            "skip": "⏭️ Skip",
            "no": "❌ No (Abort)"
        }
        selected_label = labels.get(self.user_response, self.user_response)
        
        await query.edit_message_text(
            text=f"{query.message.text}\n\n*Selected on Phone:* `{selected_label}`",
            parse_mode="Markdown"
        )
        if self.response_event:
            self.response_event.set()

    async def handle_custom_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != self.chat_id:
            return
        self.user_response = update.message.text
        await update.message.reply_text(f"✅ *Response Sent to Terminal:* `{self.user_response}`", parse_mode="Markdown")
        if self.response_event:
            self.response_event.set()

    async def prompt(self, prompt_text: str):
        self.response_event = asyncio.Event()
        self.user_response = None

        app = Application.builder().token(self.bot_token).build()
        app.add_handler(CallbackQueryHandler(self.handle_button))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_custom_text))

        # 4 Interactive Buttons matching your terminal approval options
        keyboard = [
            [
                InlineKeyboardButton("✅ 1. Yes (Proceed)", callback_data="yes"),
            ],
            [
                InlineKeyboardButton("⚙️ 2. Yes, with settings", callback_data="yes_settings"),
            ],
            [
                InlineKeyboardButton("⏭️ 3. Skip", callback_data="skip"),
                InlineKeyboardButton("❌ 4. No (Abort)", callback_data="no"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        msg = f"🔔 *Terminal Approval Request*\n\n{prompt_text}\n\n_Select an option or reply with instructions:_"
        await app.bot.send_message(chat_id=self.chat_id, text=msg, reply_markup=reply_markup, parse_mode="Markdown")
        print(f"\n=======================================================")
        print(f" [Telegram Bridge] Request sent to phone: @codeprovBot")
        print(f" Prompt: {prompt_text}")
        print(f" Waiting for your selection on mobile...")
        print(f"=======================================================\n")

        await self.response_event.wait()

        await app.updater.stop()
        await app.stop()
        await app.shutdown()

        return self.user_response

def main():
    prompt_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Proceed with terminal execution?"
    bridge = TelegramApprovalBridge(BOT_TOKEN, CHAT_ID)
    decision = asyncio.run(bridge.prompt(prompt_text))
    
    print(f"\n>>> [Phone Selection Received]: {decision.upper()}")
    
    # Exit codes:
    # 0 = Yes
    # 2 = Yes, with settings
    # 3 = Skip
    # 1 = No / Abort
    if decision in ["yes", "1", "y"]:
        return 0
    elif decision in ["yes_settings", "2"]:
        return 2
    elif decision in ["skip", "3"]:
        return 3
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
