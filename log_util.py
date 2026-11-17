import logging
import time
import sys

from datetime import datetime, UTC
from pathlib import Path

def get_logger(
    name: str, 
    log_dir_path: Path, 
    wants_console_logger: bool, 
    log_level: int = logging.INFO
    ) -> logging.Logger:


    logger: logging.Logger = logging.getLogger(name=name)
    # already has a set up logger, dont stack extra stuff
    if (logger.handlers):
        return logger

    logger.setLevel(level=log_level)
    logger.propagate = False

    log_format: logging.Formatter = logging.Formatter(fmt="[%(levelname)s] => %(asctime)s UTC => %(name)s => %(message)s")
    log_format.converter = time.gmtime

    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_file_path: Path = log_dir_path / f"log_{datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")}_UTC.log"
    
    file_handler: logging.FileHandler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)


    if (wants_console_logger):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

    logger.info("LOGGER INITAIALISED OK")
    return logger
    
