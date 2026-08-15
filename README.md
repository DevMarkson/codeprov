# Telegram Approval Bridge Setup & Usage

## 1. Files in this Directory
- **`tg_approve.py`**: The Telegram interactive approval bridge script.
- **`.env`**: Contains your secret `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (protected from Git).
- **`.gitignore`**: Ensures `.env` is never committed.
- **`.env.example`**: Safe environment template for sharing/version control.

---

## 2. Usage Examples

### Direct Command Line Check
```powershell
python tg_approve.py "Antigravity wants to run: git push origin main"
```

Exit Codes:
- `0`: Yes (Proceed)
- `2`: Yes, with settings
- `3`: Skip
- `1`: No (Abort)

### In PowerShell Scripts
```powershell
python tg_approve.py "Do you want to proceed with the deploy?"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Proceeding with deployment..."
} else {
    Write-Host "Action not approved."
}
```

### In Python Scripts
```python
import asyncio
from tg_approve import TelegramApprovalBridge, BOT_TOKEN, CHAT_ID

bridge = TelegramApprovalBridge(BOT_TOKEN, CHAT_ID)
response = asyncio.run(bridge.prompt("Do you approve running this task?"))

if response in ["yes", "1", "y"]:
    print("Executing task...")
```
