import logging
from config import LOG_FILE


def setup_logger():
    """
    Production-level logger:
    - Logs to file (app.log)
    - Logs to console (terminal)
    """

    logging.basicConfig(
        level=logging.INFO,

        # 🔥 Better readable format
        format="%(asctime)s | %(levelname)s | %(message)s",

        handlers=[
            # 📄 Save logs to file
            logging.FileHandler(LOG_FILE, encoding="utf-8"),

            # 💻 Show logs in terminal (VERY IMPORTANT)
            logging.StreamHandler()
        ]
    )