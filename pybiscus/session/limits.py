from flask import Flask, request

# a request is read into memory whole: without a bound, anyone allowed to call a component could
# exhaust its memory. Configurations, logs, metrics and vignettes are far below
REQUEST_MAX_BYTES = 16 * 1024 * 1024
# a model put in the manager's mailbox (link transport "manager"): it stays in memory until taken
MODEL_MAX_BYTES = 1024 * 1024 * 1024


def limit_request_size(app: Flask) -> None:
    app.config["MAX_CONTENT_LENGTH"] = REQUEST_MAX_BYTES


def allow_model_size() -> None:
    """called by a route receiving a model, before it reads the body"""
    request.max_content_length = MODEL_MAX_BYTES
