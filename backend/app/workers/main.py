import logging
import signal
import time
from types import FrameType

from app.core.config import get_settings
from app.core.db import create_db_engine, database_is_ready

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
running = True


def stop(_signum: int, _frame: FrameType | None) -> None:
    global running
    running = False


def run() -> None:
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("worker_started")
    while running:
        database_is_ready(engine)
        time.sleep(5)
    engine.dispose()
    logger.info("worker_stopped")


if __name__ == "__main__":
    run()
