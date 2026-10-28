"""Näkymä: rushes of a web application's pages, shot while a driver plays it, then edited into a video and
screenshots. Nothing here knows the application: the driver names the views, their panels and the
events; the cut names the scenes and the screenshots."""

from .editing import edit
from .shooting import Shooting, log

__all__ = ["Shooting", "edit", "log"]
