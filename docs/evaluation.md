# Federated evaluation of an ONNX model

A model trained elsewhere, shipped as a single `.onnx` file, is evaluated by each site on its own
data: no training, no aggregation, no code of the model's provider. What comes back is a table, one
row per site, and the server's test on a reference set.

Typical uses: compare a vendor's model on the data of several hospitals or plants before buying it;
check how a model trained on some sites generalises to sites it never saw; follow a deployed model's
quality site by site.

## How it works

Three plugins and a core option, no change to the federated loop:

| piece | role |
|---|---|
| `onnxmodel` model ([reference](plugins-reference.md#onnxmodel--onnx-model-evaluation-only)) | runs the `.onnx` file with onnxruntime: a model without any torch parameter, which refuses to train |
| `evaluateonly` strategy decorator ([reference](plugins-reference.md#evaluateonly--evaluateonly)) | no client is asked to train: each round evaluates the server's model on the server's test data and on each client's validation data, and writes the per-site report |
| `server_run.reporting.onnx_export.external_data: false` | the export at the end of a training session writes one file, the weights inside: the form `onnxmodel` evaluates |

The roles, as in a federated benchmark:

- **the organiser** publishes the file and its SHA-256, and runs the server, which tests the model on
  a reference set (the server's `data` section, mandatory);
- **each site** deposits the file, at the same path on every site in a session (the session imposes
  the path and the hash), and evaluates it on its `val` section;
- **the model's provider** gives the file only. The graph must hold its preprocessing
  (normalisation, resizing): the batches reach it as the data plugin produces them.

## Quick start (one machine)

```bash
# 1. a short MNIST session that exports its final model (configs/mnist_cnn/distributed/server.yml)
launch/uv/mnist_cnn/distributed/server.sh      # then client1.sh and client2.sh, in two other shells

# 2. publish its model as the file the evaluation reads (experiments/published/mnist_cnn.onnx)
launch/uv/onnx_eval/prepare.sh                 # prints its SHA-256

# 3. the evaluation: a server and two clients, one round, nothing trains
launch/uv/onnx_eval/server.sh                  # then client1.sh and client2.sh
```

The file and its hash come from `PYBISCUS_ONNX_MODEL` and `PYBISCUS_ONNX_SHA256`
(`launch/uv/onnx_eval/common.sh` computes the hash of the local file, which suits one machine only:
on several, the organiser gives it and each site sets it). Without them, the configurations'
default hash refuses every file.

## Configuration

The model, the same on the server and the clients
([configs/onnx_eval/](../configs/onnx_eval/)):

```yaml
model:
  name: onnxmodel
  config:
    path: experiments/published/mnist_cnn.onnx
    sha256: 28b030bd…                     # 64 hexadecimal digits: another file is refused
    output_kind: logits                   # logits, probabilities, labels or regression
    # input_name, output_name: the graph's only input and its first output by default
    # providers: [CUDAExecutionProvider, CPUExecutionProvider]   # each site its own
```

| `output_kind` | metrics |
|---|---|
| `logits` | `loss` (cross-entropy), `accuracy` |
| `probabilities` | `loss` (cross-entropy of the probabilities), `accuracy` |
| `labels` (class indices) | `loss` (the error rate: no score to take a cross-entropy of), `accuracy` |
| `regression` | `loss` (mean squared error), `mae` |

The server's pipeline:

```yaml
server_run:
  num_rounds: 1           # the model does not change from one round to the next
server_strategy:
  pipeline:
  - name: evaluateonly
    config:
      report_name: evaluation
```

The file is refused, and the run stops at its launch, when its SHA-256 differs from the
configuration's, when it is larger than `max_size_mb` (2 GB at most, the limit of a single ONNX
file), or when it keeps tensors in external data files (`model.onnx.data`: the hash would not cover
the weights). The bytes hashed are the bytes run, read once. To embed external data:
`onnx.save_model(onnx.load(path), path, save_as_external_data=False)`, or
`torch.onnx.export(..., external_data=False)`.

## The report

At each round, `evaluation.json` and `evaluation.csv` in the server's reporting directory:

```
round,site,num_examples,loss,accuracy
1,server,,0.031071,0.9899
1,0,3000,0.039259,0.9873
1,1,3000,0.028556,0.9917
1,weighted_mean,6000,0.033907,0.9895
```

`evaluation.json` also names the model evaluated (its configuration, its hash) and the number of
sites that failed. The weighted mean is Flower's own aggregate of the sites. The server does not
report its number of examples.

## In a session of the manager

Choose the *ONNX model (evaluation only)* model in the session's configuration and set its path and
hash: they are imposed and locked on every form, the providers left to each site. The server's form
needs the `evaluateonly` decorator in its pipeline.

![The evaluation panel](images/session_evaluation.png "The evaluation panel")

The manager shows the *evaluation* panel in place of its two charts: a bar per site, sorted, the
server's test and the sites' weighted mean across them, the scale fitted to the values (*0–1* for the
whole scale) ([details](sessionmanager.md#7-follow-the-session)). The metrics table keeps its row per
site.

## What leaves a site

Its metrics on its validation data (loss, accuracy or mae, its number of examples) and the logs of its
runs, as in any session. No prediction, no example, no update of the model: the parameters the
server sends are empty.

## Limits

- **Not with** `server_run.schedule` **nor** `stop_without_new_data`: a round in which no client
  trained is not counted there, and the evaluation never ends.
- **One file up to 2 GB**: a larger model needs external data, refused for now.
- **Standard operators only**: no custom operator library is loaded.
- **The `val` section**: a site evaluates on its validation data; choosing its `test` section is not
  offered yet.
- **Accuracy, loss, mae**: averaged over the batches, weighted by their examples; metrics that do not
  add up that way (F1, AUC) are not computed exactly yet.
- **A wrong input contract gives plausible but wrong metrics**: check a new model once against the
  framework it was trained with (`launch/ci/smoke.sh evaluation` does it for the MNIST demo: ONNX and
  torch agree within 1e-4 on the server and on each site).

## Related work

Federated evaluation, or *model-to-data*, exists in other frameworks; they carry the model in their
own format or in a container:

- MedPerf (MLCommons), federated benchmarking of medical AI: models in MLCube containers, a
  committee fixing the data preparation, the reference model and the metrics; only the metrics leave
  a site. Karargyris et al., *Federated benchmarking of medical artificial intelligence with
  MedPerf*, Nature Machine Intelligence 5, 799–810 (2023), doi:10.1038/s42256-023-00652-2.
- NVIDIA FLARE, [cross-site model evaluation](https://nvflare.readthedocs.io/en/2.5/programming_guide/controllers/cross_site_model_evaluation.html):
  every model evaluated by every site, a matrix of the results.
- OpenFL, [federated evaluation](https://openfl.readthedocs.io/en/v1.8/about/features_index/fed_eval.html):
  a plan reduced to a validation pass, the evaluation phase of the FeTS challenge (Pati et al.,
  *The Federated Tumor Segmentation (FeTS) Challenge*, arXiv:2105.05874, 2021).
- Flower, [federated evaluation](https://flower.ai/docs/framework/main/en/explanation-federated-evaluation.html)
  (`fraction_evaluate`, `evaluate_fn`).
- Wang et al., *Federated Evaluation of On-device Personalization*, arXiv:1910.10252 (2019).
- Guinney and Saez-Rodriguez, *Alternative Models for Sharing Confidential Biomedical Data*, JMIR
  2020, doi:10.2196/18087: the model-to-data framework, and its limits.

Here the model travels as an ONNX file, verified by its hash, run by the same runtime on every
site, without the provider's code or container.
