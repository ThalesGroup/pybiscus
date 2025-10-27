from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

from pybiscus.plugin.registries.logger_registry import _logger_modules
from pybiscus.plugin.registries.metriclogger_registry import _metricslogger_modules
from pybiscus.plugin.registries.data_registry import _data_modules
from pybiscus.plugin.registries.model_registry import _model_modules
from pybiscus.plugin.registries.strategy_registry import _strategy_modules
from pybiscus.plugin.registries.strategydecorator_registry import _strategydecorator_modules
from pybiscus.plugin.registries.client_registry import _client_modules
from pybiscus.plugin.registries.resultmodifier_registry import _resultmodifier_modules
from pybiscus.plugin.registries.flowerfitresultagregator_registry import _flowerfitresultsaggregator_modules

plugins_by_category = get_plugins_by_category()

if __name__ == "__main__":
    print(f'Logger plugins : {plugins_by_category["logger"]} {_logger_modules}')
    print(f'MetricsLogger plugins : {plugins_by_category["metricslogger"]} {_metricslogger_modules}')
    print(f'Data plugins : {plugins_by_category["data"]} {_data_modules}')
    print(f'Model plugins : {plugins_by_category["model"]} {_model_modules}')
    print(f'Strategy plugins : {plugins_by_category["strategy"]} {_strategy_modules }')
    print(f'StrategyDecorator plugins : {plugins_by_category["strategydecorator"]} {_strategydecorator_modules }')
    print(f'Client plugins : {plugins_by_category["client"]} {_client_modules }')
    print(f'ResultModifier plugins : {plugins_by_category["resultmodifier"]} {_resultmodifier_modules }')
    print(f'FlowerFitResultsAggregator plugins : {plugins_by_category["flowerfitresultsaggregator"]} {_flowerfitresultsaggregator_modules }')

