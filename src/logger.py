from loguru import logger
import sys

logger.remove()

# console logger
logger.add(sys.stdout, level="DEBUG", format="{time} - {name} - {level} - {message}")
debug_logger = logger