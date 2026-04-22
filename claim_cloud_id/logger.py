import logging
from pathlib import Path

LOGGER = logging.getLogger("claim_cloud_id")
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False


def log_info(message: str) -> None:
    if LOGGER.handlers:
        LOGGER.info(message)


def log_warning(message: str) -> None:
    if LOGGER.handlers:
        LOGGER.warning(message)


def log_error(message: str) -> None:
    if LOGGER.handlers:
        LOGGER.error(message)


def emit_info(message: str) -> None:
    print(message)
    log_info(message)


def emit_warning(message: str) -> None:
    print(message)
    log_warning(message)


def emit_error(message: str) -> None:
    print(message)
    log_error(message)


def setup_file_logger(log_file_path: str) -> str:
    path = Path(log_file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    for handler in list(LOGGER.handlers):
        LOGGER.removeHandler(handler)
        handler.close()

    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)

    return str(path)
