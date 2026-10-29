import importlib

# imported on demand: the linter needs one family's interface without loading every registry
FAMILY_INTERFACES = {
    "data": ("lightning.pytorch", "LightningDataModule"),
    "model": ("lightning.pytorch", "LightningModule"),
    "client": ("pybiscus.interfaces.flower.clientfactory", "ClientFactory"),
    "logger": ("pybiscus.interfaces.core.logger", "LoggerFactory"),
    "metricslogger": ("pybiscus.interfaces.core.metricsloggerfactory", "MetricsLoggerFactory"),
    "strategy": ("pybiscus.interfaces.flower.fabricstrategyfactory", "FabricStrategyFactory"),
    "strategydecorator": ("pybiscus.interfaces.flower.strategydecorator", "StrategyDecorator"),
    "resultmodifier": ("pybiscus.interfaces.flower.resultmodifier", "ResultModifier"),
    "flowerfitresultsaggregator": ("pybiscus.interfaces.flower.flowerfitresultsaggregator", "FlowerFitResultsAggregator"),
    "stoppingcriterion": ("pybiscus.interfaces.flower.stoppingcriterion", "StoppingCriterion"),
}


def family_interface(category: str) -> type:
    module, name = FAMILY_INTERFACES[category]
    return getattr(importlib.import_module(module), name)
