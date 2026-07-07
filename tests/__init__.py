"""Force mock mode for the entire test suite.

Unit tests must be deterministic, free, and fast regardless of whatever real
API keys happen to be sitting in a developer's local .env. This runs before
any test module imports revops_copilot.config, so it wins over python-dotenv's
load_dotenv() call in that module (os.environ.get with a real value already
present would otherwise leak into every test run).
"""
import os

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("OPIK_API_KEY", None)
os.environ["ANTHROPIC_API_KEY"] = ""
