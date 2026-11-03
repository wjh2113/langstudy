"""Restore module-wide fakes used by the legacy standalone test scripts."""
import sys
import time
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config
import app


@pytest.fixture(autouse=True)
def isolated_globals():
    state = dict(vars(config))
    sleep = time.sleep
    modules = {k: sys.modules.get(k) for k in ('httpx', 'app.gateway')}
    gateway = getattr(app, 'gateway', None)
    # Unit tests never fall through to real provider credentials.
    config.GATEWAY_API_KEY = ''
    config.LLM_API_KEY = ''
    yield
    for key, value in state.items():
        setattr(config, key, value)
    time.sleep = sleep
    for key, value in modules.items():
        if value is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = value
    if gateway is None:
        app.__dict__.pop('gateway', None)
    else:
        app.gateway = gateway
