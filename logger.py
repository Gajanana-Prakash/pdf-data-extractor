import logging


def setup_logger():
    """
    Configures the root logger to write INFO-level messages to app.log.

    FIX (Warning 2): Added encoding="utf-8" to the FileHandler.
    Without this, on Windows the log file uses the system default encoding
    (often cp1252), which crashes when logging messages contain Unicode
    characters such as rupee signs (₹) or special symbols.

    Also: emojis have been removed from log messages in main.py.
    Emojis are multi-byte Unicode characters that can cause encoding
    errors on some Windows terminals and log viewers.
    """
    logging.basicConfig(
        filename="app.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8"        # FIX: prevents Unicode/encoding errors on Windows
    )