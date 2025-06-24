
"""
PyTorch Lightning – TensorBoardLogger

...

from pytorch_lightning.loggers import TensorBoardLogger

logger = TensorBoardLogger("logs", name="my_model")

...

logger.log_hyperparams(params: dict)

logger.log_hyperparams({"lr": 0.001, "batch_size": 32})

...

logger.experiment

logger.experiment.add_scalar("loss/train", 0.25, step=1)
logger.experiment.add_text("info", "Training started", step=1)
logger.experiment.add_histogram("weights", model.layer.weight, step=1)

...

logger.log_metrics(metrics: dict, step: Optional[int])

logger.log_metrics({"accuracy": 0.93}, step=10)

...

logger.save_dir

print(logger.save_dir)  # e.g., "logs"

...

logger.name, logger.version, logger.log_dir

print(logger.name)       # "my_model"
print(logger.version)    # "version_0"
print(logger.log_dir)    # logs/my_model/version_0

"""
class MetricsLoggerFactory:
    
    def get_metricslogger(self,reporting_path):
        pass
