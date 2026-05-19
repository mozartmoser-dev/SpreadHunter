import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def notify(self, message: str) -> bool:
        if not self.is_configured():
            logger.warning("TelegramNotifier: Not configured.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(self.api_url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                logger.error("Telegram API error: %s", data)
                return False
            return True
        except Exception as e:
            logger.exception("Failed to send Telegram message: %s", e)
            return False
