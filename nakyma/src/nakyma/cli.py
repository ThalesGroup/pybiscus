"""nakyma edit <rushes> <cut> [--output]: the cut's video and screenshots;
nakyma ui <rushes> <cut>: the interactive editor (edit --ui as well). Also python -m nakyma."""

import argparse
import shutil
from pathlib import Path

from ruamel.yaml import YAML

from .editing import edit


def load_cut(cut_file):
    # the same reader as the interactive editor's: a cut reads the same in both
    return YAML(typ="safe").load(Path(cut_file).read_text()) or {}


def edit_file(rushes, cut_file, output=None):
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is needed to edit the video: install it first (Debian: apt install ffmpeg)")
    cut = load_cut(cut_file)
    if output and cut.get("shots") and not cut.get("scenes"):
        # a cut of screenshots only: --output is their directory
        cut["shots_dir"] = str(output)
        output = None
    return edit(rushes, cut, output)


def run_editor(rushes, cut_file, port=0, open_browser=True):
    # imported here: the editor's server is not needed to edit from the command line
    from .editor import serve
    return serve(rushes, cut_file, port, open_browser)


def add_edit_arguments(parser):
    parser.add_argument("rushes", type=Path)
    parser.add_argument("cut", type=Path)
    parser.add_argument("--output", type=Path, help="basename of the video, or directory of the screenshots, instead of the cut's")
    parser.add_argument("--ui", action="store_true", help="open a local page: the rushes on a timeline, the cut's images, the video played")
    add_ui_arguments(parser)


def add_ui_arguments(parser):
    parser.add_argument("--port", type=int, default=0, help="with --ui: port of the page (default: a free one)")
    parser.add_argument("--no-browser", action="store_true", help="with --ui: give the page's address without opening it")


def run(args):
    if getattr(args, "ui", False) or args.command == "ui":
        return run_editor(args.rushes, args.cut, args.port, not args.no_browser)
    edit_file(args.rushes, args.cut, args.output)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nakyma", description="Näkymä: rushes of web pages edited into videos and screenshots")
    sub = parser.add_subparsers(dest="command", required=True)
    add_edit_arguments(sub.add_parser("edit", help="edit rushes with a cut: the scenes into a video, the screenshots"))
    ui = sub.add_parser("ui", help="the interactive editor: the rushes on a timeline, the cut changed and saved, the export")
    ui.add_argument("rushes", type=Path)
    ui.add_argument("cut", type=Path)
    add_ui_arguments(ui)
    return run(parser.parse_args(argv))
