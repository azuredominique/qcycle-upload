import os
import logging

logger = logging.getLogger(__name__)


def temp_join(tmp_directory, path):
    return os.path.join(tmp_directory, path)
