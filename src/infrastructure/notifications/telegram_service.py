import logging
from src.infrastructure.notifications.telegram_notifier import TelegramNotifier
from src.infrastructure.persistence.repositories.repositories import ParametroRepository

logger = logging.getLogger(__name__)

class TelegramService:
    """Facade that reads telegram configuration from the DB and sends messages.
    It respects the "notif_telegram_enable" flag.
    """

    def __init__(self, db_path=None):
        self.param_repo = ParametroRepository(db_path)
        self._notifier: TelegramNotifier | None = None
        import time
        self._last_sent_time = 0.0
        self._min_interval_seconds = 3.0  # Evita sobrecarregar a API com limite de 3 segundos

    def _load_params(self) -> dict[str, str]:
        """Fetch token, chat_id and enable flag from the parameters table.
        Returns a dict with keys 'token', 'chat_id', 'enable'. Missing values are empty strings.
        """
        token = self.param_repo.get_by_chave("telegram_bot_token")
        chat_id = self.param_repo.get_by_chave("telegram_chat_id")
        enable = self.param_repo.get_by_chave("notif_telegram_enable")
        return {
            "token": token.valor if token else "",
            "chat_id": chat_id.valor if chat_id else "",
            "enable": str(enable.valor) if enable else "0",
        }

    def _build_notifier(self) -> TelegramNotifier | None:
        if self._notifier is not None:
            return self._notifier
        cfg = self._load_params()
        token = cfg.get("token", "")
        chat_id = cfg.get("chat_id", "")
        if token and chat_id and token != "0" and chat_id != "0":
            self._notifier = TelegramNotifier(token, chat_id)
            return self._notifier
        return None

    def is_enabled(self) -> bool:
        cfg = self._load_params()
        try:
            enable_val = float(cfg.get("enable", "0"))
        except ValueError:
            enable_val = 0.0
        token = cfg.get("token", "")
        chat_id = cfg.get("chat_id", "")
        return (
            enable_val == 1.0 
            and bool(token) 
            and token != "0" 
            and bool(chat_id) 
            and chat_id != "0"
        )

    def send(self, message: str) -> bool:
        if not self.is_enabled():
            logger.info("Telegram notifications disabled via config.")
            return False
            
        import time
        now = time.time()
        if now - self._last_sent_time < self._min_interval_seconds:
            logger.info("Telegram message skipped to avoid spam (throttled).")
            return False

        notifier = self._build_notifier()
        if not notifier:
            logger.warning("TelegramService: Notifier could not be built (missing token/chat_id).")
            return False
        
        success = notifier.notify(message)
        if success:
            self._last_sent_time = now
        return success
