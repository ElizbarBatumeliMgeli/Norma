"""Where NORMA keeps its data, and how it reaches an AI: a Claude (Anthropic) key, a Google Cloud project for
Gemini on Vertex AI (signed in with `gcloud auth application-default login`), or a Gemini API key.

The first of those that is set does the checks and the chat.
"""
import json
import os
from pathlib import Path

HOME = Path(os.environ.get('NORMA_HOME') or Path.home() / '.norma')
CONFIG = HOME / 'config.json'
REPORTS = HOME / 'reports'

PROVIDERS = ('claude', 'vertex', 'gemini')
SAVED_AS = dict(claude='anthropic_key', vertex='vertex', gemini='api_key')   # `api_key` held the Gemini key before Claude was added
ENVIRONMENT = dict(claude=('ANTHROPIC_API_KEY',), gemini=('GEMINI_API_KEY', 'GOOGLE_API_KEY'))
DEFAULT_LOCATION = 'global'


def saved():
    try:
        return json.loads(CONFIG.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


def read_key(provider='gemini'):
    """The key saved in the app, else the provider's environment variable."""
    return saved().get(SAVED_AS[provider]) or next((os.environ[name] for name in ENVIRONMENT[provider] if os.environ.get(name)), None)


def vertex():
    """The Google Cloud project and region for Gemini on Vertex AI, from Settings or NORMA_VERTEX_PROJECT; else None."""
    place = saved().get('vertex') or {}
    project = place.get('project') or os.environ.get('NORMA_VERTEX_PROJECT')
    if not project:
        return None
    return dict(project=project, location=place.get('location') or os.environ.get('NORMA_VERTEX_LOCATION') or DEFAULT_LOCATION)


def connected():
    """Which ways to an AI are set up."""
    return dict(claude=bool(read_key('claude')), vertex=bool(vertex()), gemini=bool(read_key('gemini')))


def provider_of(key):
    """Which service a key belongs to: Anthropic keys start with sk-ant-."""
    return 'claude' if key.startswith('sk-ant-') else 'gemini'


def provider():
    """The AI that checks drawings: Claude when it has a key, else Gemini on Vertex, else Gemini with a key, else None."""
    ways = connected()
    return next((name for name in PROVIDERS if ways[name]), None)


def write(config):
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG.touch(mode=0o600)
    CONFIG.chmod(0o600)
    CONFIG.write_text(json.dumps(config), encoding='utf-8')


def save_key(key):
    """Saves a key under the provider it belongs to, keeping the other provider's key."""
    write(dict(saved(), **{SAVED_AS[provider_of(key)]: key}))


def save_vertex(project, location):
    write(dict(saved(), vertex=dict(project=project, location=location or DEFAULT_LOCATION)))


def forget_key(provider=None):
    """Forgets one provider's key, or every key."""
    config = {} if provider is None else {k: v for k, v in saved().items() if k != SAVED_AS[provider]}
    if config:
        write(config)
    else:
        CONFIG.unlink(missing_ok=True)
