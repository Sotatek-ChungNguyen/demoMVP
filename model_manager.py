import os
import hashlib
import logging
import requests
from tqdm import tqdm

logger = logging.getLogger(__name__)

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "hand_landmarker.task")
EXPECTED_SHA256 = None  # Set after first verified download; skip check if None


def _download_model(url: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    logger.info("Downloading hand_landmarker.task ...")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc="hand_landmarker.task") as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))


def _verify_sha256(path: str, expected: str) -> bool:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            sha.update(block)
    actual = sha.hexdigest()
    if actual != expected:
        logger.error("SHA256 mismatch: expected %s, got %s", expected, actual)
        return False
    return True


def ensure_model() -> str:
    if os.path.isfile(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 0:
        if EXPECTED_SHA256 and not _verify_sha256(MODEL_PATH, EXPECTED_SHA256):
            logger.warning("Cached model failed checksum, re-downloading ...")
            os.remove(MODEL_PATH)
        else:
            return MODEL_PATH

    _download_model(MODEL_URL, MODEL_PATH)

    if EXPECTED_SHA256 and not _verify_sha256(MODEL_PATH, EXPECTED_SHA256):
        raise RuntimeError("Downloaded model failed SHA256 verification")

    if os.path.getsize(MODEL_PATH) == 0:
        os.remove(MODEL_PATH)
        raise RuntimeError("Downloaded model file is empty")

    logger.info("Model ready at %s", MODEL_PATH)
    return MODEL_PATH
