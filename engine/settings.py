"""Where NORMA keeps its data, and the Gemini API key."""
import json
import os
from pathlib import Path

HOME = Path(os.environ.get('NORMA_HOME') or Path.home() / '.norma')
CONFIG = HOME / 'config.json'
REPORTS = HOME / 'reports'


def read_key():
    """The key saved in the app, else GEMINI_API_KEY or GOOGLE_API_KEY from the environment."""
    try:
        saved = json.loads(CONFIG.read_text(encoding='utf-8')).get('api_key')
    except FileNotFoundError:
        saved = None
    return saved or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or None


def save_key(key):
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG.touch(mode=0o600)
    CONFIG.chmod(0o600)
    CONFIG.write_text(json.dumps(dict(api_key=key)), encoding='utf-8')


def forget_key():
    CONFIG.unlink(missing_ok=True)
