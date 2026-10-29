import hashlib
from enum import Enum
from pathlib import Path
from typing import ClassVar, Literal, Optional, TypedDict, override

import lightning.pytorch as pl
import numpy as np
import onnx
import onnxruntime as ort
import torch
import torch.nn.functional as F
from pydantic import BaseModel, ConfigDict, Field, model_validator

import pybiscus.core.pybiscus_logger as logm
from pybiscus.core.pybiscusexception import PybiscusValueException
from pybiscus.ml.classrates import class_rate_keys, class_rates


# Enums and not Literals: the agent's form offers an Enum's values, a Literal's first only
class OutputKind(str, Enum):
    logits = "logits"
    probabilities = "probabilities"
    labels = "labels"
    regression = "regression"


OutputKind.PYBISCUS_DESCRIPTIONS = {
    "logits": "scores before a softmax: loss (cross-entropy) and accuracy",
    "probabilities": "a softmax's output: loss (cross-entropy of the probabilities) and accuracy",
    "labels": "class indices: loss (the error rate) and accuracy",
    "regression": "values: loss (mean squared error) and mae",
}


class ClassRates(str, Enum):
    none = "none"
    per_class = "per_class"
    confusion_matrix = "confusion_matrix"


ClassRates.PYBISCUS_DESCRIPTIONS = {
    "none": "no per-class figure",
    "per_class": "true and false positives, false negatives of each class, as shares of the examples: an exact F1",
    "confusion_matrix": "those and every cell of the confusion matrix",
}

# onnxruntime's input types and the numpy arrays it accepts for them
ONNX_TO_NUMPY = {
    "tensor(float)": np.float32,
    "tensor(double)": np.float64,
    "tensor(float16)": np.float16,
    "tensor(int64)": np.int64,
    "tensor(int32)": np.int32,
    "tensor(uint8)": np.uint8,
    "tensor(bool)": np.bool_,
}


class ConfigOnnxModel(BaseModel):
    """a trained model shipped as an ONNX file, evaluated without its code (federated evaluation)"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    path: str = Field(description="the .onnx file, deposited by each site")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$",
                        description="SHA-256 of the file, given by the session's organiser: another file is refused")
    output_kind: OutputKind = Field(default=OutputKind.logits,
                                    description="what the graph outputs: logits, probabilities, labels (class indices) or regression values")
    input_name: Optional[str] = Field(default=None, description="the graph's input to feed, its only input by default")
    output_name: Optional[str] = Field(default=None, description="the graph's output to read, its first output by default")
    # a session imposes the file and its SHA-256 on every site but leaves the providers to each (a GPU site)
    providers: list[str] = Field(default=["CPUExecutionProvider"], min_length=1,  # pybiscus-lint: ignore=model-hyperparameters
                                 description="onnxruntime execution providers, by order of preference")
    max_size_mb: int = Field(default=2048, ge=1, le=2048,
                             description="a larger file is refused before being read (a single ONNX file stops at 2 GB)")
    num_classes: Optional[int] = Field(default=None, ge=2, le=1000,
                                       description="the number of classes, needed by class_rates")
    class_rates: ClassRates = Field(default=ClassRates.none,
                                    description="per-class figures for an exact F1; per_class and confusion_matrix tell the site's share of each class")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def rates_need_classes(self):
        if self.class_rates != ClassRates.none:
            if self.num_classes is None:
                raise ValueError("class_rates needs num_classes")
            if self.output_kind == OutputKind.regression:
                raise ValueError("class_rates is for a classification, not with output_kind regression")
        return self


class ConfigModel_OnnxModel(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "ONNX model (evaluation only)"

    name: Literal["onnxmodel"]
    config: ConfigOnnxModel

    model_config = ConfigDict(extra="forbid")


class OnnxClassificationSignature(TypedDict):
    loss: torch.Tensor
    accuracy: torch.Tensor


class OnnxRegressionSignature(TypedDict):
    loss: torch.Tensor
    mae: torch.Tensor


def with_rate_keys(signature, keys: list[str]):
    return TypedDict(f"{signature.__name__}WithRates", {**signature.__annotations__, **{key: torch.Tensor for key in keys}})


def verified_model_bytes(path: str, sha256: str, max_size_mb: int) -> bytes:
    file = Path(path).expanduser()
    if not file.is_file():
        raise PybiscusValueException(f"onnxmodel: no file {file}")
    size = file.stat().st_size
    if size > max_size_mb * 1024 * 1024:
        raise PybiscusValueException(f"onnxmodel: {file} is {size / 2**20:.0f} MB, more than max_size_mb {max_size_mb}")
    # the bytes hashed are the bytes run: reading the file again would let it change in between
    content = file.read_bytes()
    found = hashlib.sha256(content).hexdigest()
    if found != sha256:
        raise PybiscusValueException(f"onnxmodel: {file} has SHA-256 {found}, the session expects {sha256}")
    # the hash covers this file only: weights in a side file (torch.onnx.export's .onnx.data) would go unverified
    graph = onnx.load_model_from_string(content)
    external = [t.name for t in graph.graph.initializer if t.data_location == onnx.TensorProto.EXTERNAL]
    if external:
        raise PybiscusValueException(
            f"onnxmodel: {file} keeps {len(external)} tensors in external data files, not covered by its SHA-256; "
            f"embed them: onnx.save_model(onnx.load(path), path, save_as_external_data=False), "
            f"or torch.onnx.export(..., external_data=False)")
    return content


class LitOnnxModel(pl.LightningModule):
    """Evaluates an ONNX graph on the site's data: no torch parameter, nothing to train or aggregate.
    The graph includes its preprocessing; the batch's inputs are given to it as they come from the data plugin."""

    @override
    def __init__(self, path: str, sha256: str, output_kind: OutputKind = OutputKind.logits,
                 input_name: Optional[str] = None, output_name: Optional[str] = None,
                 providers: Optional[list[str]] = None, max_size_mb: int = 2048,
                 num_classes: Optional[int] = None, class_rates: ClassRates = ClassRates.none):
        super().__init__()
        self.save_hyperparameters()

        content = verified_model_bytes(path, sha256, max_size_mb)
        options = ort.SessionOptions()
        options.log_severity_level = 3
        self.session = ort.InferenceSession(content, sess_options=options,
                                            providers=providers or ["CPUExecutionProvider"])

        inputs = self.session.get_inputs()
        if input_name is None and len(inputs) != 1:
            raise PybiscusValueException(f"onnxmodel: the graph has {len(inputs)} inputs {[i.name for i in inputs]}, set input_name")
        graph_input = next((i for i in inputs if input_name in (None, i.name)), None)
        if graph_input is None:
            raise PybiscusValueException(f"onnxmodel: no input {input_name} in the graph, it has {[i.name for i in inputs]}")
        if graph_input.type not in ONNX_TO_NUMPY:
            raise PybiscusValueException(f"onnxmodel: unsupported input type {graph_input.type}")
        outputs = [o.name for o in self.session.get_outputs()]
        if output_name is not None and output_name not in outputs:
            raise PybiscusValueException(f"onnxmodel: no output {output_name} in the graph, it has {outputs}")

        self.input_name = graph_input.name
        self.input_dtype = ONNX_TO_NUMPY[graph_input.type]
        self.output_name = output_name or outputs[0]
        # a plain str: the hyperparameters saved and the comparisons below read the value
        self.output_kind = OutputKind(output_kind).value
        if output_kind == "regression":
            self._signature = OnnxRegressionSignature
        else:
            self._signature = OnnxClassificationSignature
        self.num_classes = num_classes
        self.confusion_matrix = ClassRates(class_rates) == ClassRates.confusion_matrix
        self.with_rates = ClassRates(class_rates) != ClassRates.none
        if self.with_rates:
            self._signature = with_rate_keys(OnnxClassificationSignature, class_rate_keys(num_classes, self.confusion_matrix))
        logm.console.log(f"onnxmodel: {Path(path).name} (sha256 {sha256[:12]}…), input {self.input_name} {graph_input.shape}, "
                         f"output {self.output_name}, providers {self.session.get_providers()}")

    @property
    def signature(self):
        return self._signature

    @override
    def forward(self, inputs):
        array = inputs.detach().cpu().numpy().astype(self.input_dtype, copy=False)
        (output,) = self.session.run([self.output_name], {self.input_name: array})
        return torch.from_numpy(np.asarray(output)).to(inputs.device)

    def _evaluate(self, batch):
        inputs, targets = batch
        outputs = self.forward(inputs)
        if self.output_kind == "regression":
            outputs = outputs.reshape(targets.shape).to(targets.dtype)
            return {"loss": F.mse_loss(outputs, targets), "mae": (outputs - targets).abs().mean()}
        if self.output_kind == "labels":
            predicted = outputs.reshape(targets.shape)
            accuracy = (predicted == targets).float().mean()
            # no score to take a cross-entropy of: the error rate stands for the loss
            return self._with_rates({"loss": 1 - accuracy, "accuracy": accuracy}, predicted, targets)
        outputs = outputs.float()
        if self.output_kind == "logits":
            loss = F.cross_entropy(outputs, targets)
        else:
            loss = F.nll_loss(torch.log(outputs.clamp_min(1e-12)), targets)
        predicted = outputs.argmax(dim=1)
        return self._with_rates({"loss": loss, "accuracy": (predicted == targets).float().mean()}, predicted, targets)

    def _with_rates(self, results, predicted, targets):
        if self.with_rates:
            results.update(class_rates(predicted, targets, self.num_classes, self.confusion_matrix))
        return results

    @override
    def training_step(self, batch, batch_idx):
        raise PybiscusValueException("onnxmodel only evaluates: a session using it must not train (evaluateonly decorator)")

    @override
    def validation_step(self, batch, batch_idx):
        return self._evaluate(batch)

    @override
    def test_step(self, batch, batch_idx):
        return self._evaluate(batch)

    @override
    def configure_optimizers(self):
        return None
