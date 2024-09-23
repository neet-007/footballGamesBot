import json
import logging
import logging.config
from pathlib import Path

def setup_logging():
    config_file = Path("custom_logging/logging_configs/json_stderr.json")
    with open(config_file) as f_in:
        config = json.load(f_in)

    logging.config.dictConfig(config)


