import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def additional_func():
    logger.info("additional_func")