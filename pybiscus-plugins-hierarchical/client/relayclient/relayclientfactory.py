from typing import ClassVar, Literal

import flwr as fl
from flwr.common import Code, EvaluateRes, FitRes, GetParametersRes, Status, ndarrays_to_parameters, parameters_to_ndarrays
from pydantic import BaseModel, ConfigDict

import pybiscus.core.pybiscus_logger as logm
from pybiscus.flower.sessionlink import ConfigSessionLink, DirectoryLink, make_link, SessionLinkError, scalar_metrics
from pybiscus.interfaces.flower.clientfactory import ClientFactory

# A client of the upper session standing for a whole lower session: it trains nothing, its fit
# result is the lower level's aggregate of the same round (docs/sessionmanager.md).


class ConfigFlowerRelayClient(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Relay"

    name:   Literal["relay"]
    config: ConfigSessionLink

    model_config = ConfigDict(extra="forbid")


# a Client and not a NumPyClient: it answers a failed round with a status the server counts as a
# failure, where an exception would end the process (legacy grpc-bidi transport)
class RelayClient(fl.client.Client):

    def __init__(self, cid, model, link: DirectoryLink):
        super().__init__()
        self.cid = cid
        self.model = model
        self.link = link
        self.last_round = 0

    def initialize(self):
        self.link.reset()

    def finalize(self):
        # the upper server disconnected its clients: whatever the reason, it has no round
        # last_round + 1, which the lower level's server would wait for until its timeout
        try:
            self.link.publish_end(self.last_round + 1, f"the upper level ended its session after round {self.last_round}")
        except SessionLinkError as error:
            logm.console.log(f"🔁 relay {self.cid}: the end of the session could not be sent down: {error}")

    def get_parameters(self, ins):
        arrays = [value.cpu().numpy() for value in self.model.state_dict().values()]
        return GetParametersRes(status=Status(Code.OK, "ok"), parameters=ndarrays_to_parameters(arrays))

    def fit(self, ins):
        server_round = ins.config["server_round"]
        self.last_round = server_round
        self.link.publish_model(server_round, parameters_to_ndarrays(ins.parameters))
        try:
            arrays, num_examples, metrics = self.link.wait_aggregate(server_round)
        except SessionLinkError as error:
            logm.console.log(f"🔁 relay {self.cid}: round {server_round} failed: {error}")
            return FitRes(status=Status(Code.FIT_NOT_IMPLEMENTED, str(error)), parameters=ndarrays_to_parameters([]),
                          num_examples=0, metrics={})
        logm.console.log(f"🔁 relay {self.cid}: round {server_round}, the lower level's aggregate of {num_examples} examples sent up")
        return FitRes(status=Status(Code.OK, "ok"), parameters=ndarrays_to_parameters(arrays),
                      num_examples=num_examples, metrics=scalar_metrics(metrics))

    def evaluate(self, ins):
        # a failure for the server: 0 examples would divide by zero in a session of relays only,
        # and metrics missing from the other clients' would erase every metric common to them
        return EvaluateRes(status=Status(Code.EVALUATE_NOT_IMPLEMENTED, "a relay holds no data: the lower level evaluates the model on its own"),
                           loss=0.0, num_examples=0, metrics={})


class RelayClientFactory(ClientFactory):
    """Hierarchical sessions: a client of the upper level that stands for a whole lower session; it
    trains nothing, hands the model it receives to the lower level and returns that level's
    aggregate, weighted by its examples; see hierarchical-session.md."""

    # the relay's machine (the lower level's server's) may not hold the training set
    NEEDS_DATA = False

    def __init__(self, config, data, model, num_examples):
        self.config = config
        self.model = model

    def get_client(self):
        link = make_link(self.config.flower_client.alternate_client_class.config)
        return RelayClient(self.config.client_run.cid, self.model, link)
