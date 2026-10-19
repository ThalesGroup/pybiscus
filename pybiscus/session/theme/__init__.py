# The colours of every page of the agents and of the manager, and the choice between the dark theme
# (the default) and the light one. Inlined in each page's head: the agent and the manager are two
# Flask applications, and a theme applied before the first paint does not flash.

from functools import lru_cache
from pathlib import Path

_HERE = Path(__file__).parent


@lru_cache(maxsize=1)
def theme_head() -> str:
    css = (_HERE / "theme.css").read_text(encoding="utf-8")
    js = (_HERE / "theme.js").read_text(encoding="utf-8")
    return f"<style>{css}</style>\n<script>{js}</script>"


def install(app) -> None:
    """templates write {{ pybiscus_theme_head() | safe }} in their head"""
    app.jinja_env.globals["pybiscus_theme_head"] = theme_head
