import logging
from pathlib import Path
try:
    from utils.config import LOG_ENABLED
except Exception:
    LOG_ENABLED = True


def setup_logging() -> None:
    if not LOG_ENABLED:
        logging.disable(logging.CRITICAL)
        logging.getLogger().handlers.clear()
        return
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
