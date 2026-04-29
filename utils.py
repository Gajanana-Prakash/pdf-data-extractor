import hashlib
import logging


def generate_file_hash(file_path):
    """
    Generate SHA256 hash of a file (used for duplicate detection)
    """
    sha256 = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)

        return sha256.hexdigest()

    except Exception as e:
        logging.error(f"Hash generation error: {str(e)}")
        return None