import csv
import json
from typing import ClassVar, Dict, List, Literal, Optional, Tuple, Union

from flwr.common import EvaluateRes, FitIns, Parameters, Scalar
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
from pydantic import BaseModel, ConfigDict, Field

import pybiscus.core.pybiscus_logger as logm
import pybiscus.core.pybiscuscontext as pcpc
from pybiscus.core.reportingoutputs import ReportingOutputs, output_file
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator


class ConfigEvaluateOnlyStrategyDecoratorData(ReportingOutputs):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    report_name: str = Field(default="evaluation", pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
                             description="the per-site report, <name>.json and <name>.csv in the reporting directory, written at each round")

    model_config = ConfigDict(extra="forbid")

    def reporting_outputs(self):
        return {"json": output_file(f"{self.report_name}.json"), "csv": output_file(f"{self.report_name}.csv")}


class ConfigEvaluateOnlyStrategyDecorator(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "EvaluateOnly"
    PYBISCUS_GROUP: ClassVar[str] = "Evaluation"
    name: Literal["evaluateonly"]

    config: ConfigEvaluateOnlyStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")


def plain(value):
    return value if isinstance(value, (int, float, str, bool)) or value is None else float(value)


def weighted_mean(sites: list[dict]) -> Optional[dict]:
    total = sum(site["num_examples"] for site in sites)
    if not total:
        return None
    keys = [key for key in sites[0]["metrics"] if all(isinstance(site["metrics"].get(key), (int, float)) for site in sites)]
    return {"num_examples": total,
            "loss": sum(site["loss"] * site["num_examples"] for site in sites) / total,
            "metrics": {key: sum(site["metrics"][key] * site["num_examples"] for site in sites) / total for key in keys}}


class EvaluateOnlyStrategyDecorator(StrategyDecorator):
    """No client trains: each round only evaluates the server's model, on the server's test data and on
    each client's validation data (federated evaluation, with the onnxmodel model for instance), and writes
    the per-site report: the server, each site and the sites' mean weighted by their examples.
    Not with server_run.schedule nor stop_without_new_data: a round in which no client trained is not counted there."""

    def __init__(self, base_strategy, config: ConfigEvaluateOnlyStrategyDecoratorData):
        super().__init__(base_strategy)
        self.config = config
        self.server_results: dict[int, dict] = {}
        self.rounds: list[dict] = []

    def configure_fit(self, server_round: int, parameters: Parameters, client_manager: ClientManager
                      ) -> List[Tuple[ClientProxy, FitIns]]:
        logm.console.log(f"[{server_round}] evaluateonly: no client trains in this round")
        # the server's fit_round ends on an empty list without aggregating: the parameters stay those of the start
        return []

    def evaluate(self, server_round: int, parameters: Parameters) -> Optional[Tuple[float, Dict[str, Scalar]]]:
        result = self.base_strategy.evaluate(server_round, parameters)
        if result is not None:
            loss, metrics = result
            self.server_results[server_round] = {"loss": float(loss), "metrics": {k: plain(v) for k, v in metrics.items()}}
        return result

    def aggregate_evaluate(self, server_round: int,
                           results: List[Tuple[ClientProxy, EvaluateRes]],
                           failures: List[Union[Tuple[ClientProxy, EvaluateRes], BaseException]],
                           ) -> Tuple[Optional[float], Dict[str, Scalar]]:
        aggregated = self.base_strategy.aggregate_evaluate(server_round, results, failures)
        sites = []
        for proxy, res in results:
            metrics = {k: plain(v) for k, v in res.metrics.items() if k != "cid"}
            sites.append({"cid": str(res.metrics.get("cid", proxy.cid)), "num_examples": res.num_examples,
                          "loss": float(res.loss), "metrics": metrics})
        sites.sort(key=lambda site: site["cid"])
        self.rounds.append({"round": server_round, "server": self.server_results.get(server_round),
                            "sites": sites, "weighted_mean": weighted_mean(sites) if sites else None,
                            "failures": len(failures)})
        self.write_reports()
        return aggregated

    def write_reports(self) -> None:
        model = pcpc.pybiscus_context.get(pcpc.SERVER_CONFIG, {}).get("model")
        path = self.config.output_path("json")
        path.write_text(json.dumps({"model": model, "rounds": self.rounds}, indent=2))
        rows = []
        for entry in self.rounds:
            named = [("server", entry["server"])] + [(site["cid"], site) for site in entry["sites"]] + [("weighted_mean", entry["weighted_mean"])]
            for site, values in named:
                if values is not None:
                    rows.append({"round": entry["round"], "site": site, "num_examples": values.get("num_examples", ""),
                                 "loss": values["loss"], **values["metrics"]})
        columns = list(dict.fromkeys(key for row in rows for key in row))
        with self.config.output_path("csv").open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns, restval="")
            writer.writeheader()
            writer.writerows(rows)
        logm.console.log(f"evaluateonly: report of round {self.rounds[-1]['round']}, {len(self.rounds[-1]['sites'])} site(s): {path}")
