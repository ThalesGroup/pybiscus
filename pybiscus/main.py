import sys

from pybiscus.core.pybiscusexception import PybiscusPluginError


def main():
    """Principal entry point for script pybiscus."""
    # the commands load the plugins when imported: import them here to report a plugin failure
    # cleanly instead of a traceback
    try:
        from pybiscus.commands.typer_app import app as pybiscus_typer_app
    except PybiscusPluginError as e:
        from pybiscus.commands.apps_common import PLUGIN_ERROR_EXIT_CODE
        print(f"❌ [plugins] {e}", file=sys.stderr)
        sys.exit(PLUGIN_ERROR_EXIT_CODE)
    pybiscus_typer_app()

if __name__ == "__main__":
    main()
