pybiscus_context = {}

# keys set by the server (app_server) before it builds the strategy decorators (SERVER_CONFIG
# before the metrics loggers); the client sets MODEL only. Plugins read them here rather than
# through extra constructor parameters, which would change the signature of every strategy
# factory and decorator
MODEL = "model"                    # the model, set up by Fabric
FABRIC = "fabric"
REPORTING_PATH = "reporting_path"  # pathlib.Path of this run's reporting directory
PRIVACY_SET = "privacy_set"        # the data plugin's privacy_dataloader(), set up by Fabric, or None
SERVER_CONFIG = "server_config"    # the validated server configuration (JSON-able dict), set first
