from typing import ClassVar, Literal
import flwr as fl

from flwr.server.strategy import Strategy

import numpy as np
from pydantic import BaseModel, ConfigDict
import matplotlib.pyplot as plt
import seaborn as sns

from pybiscus.core.ensure_filesystem import ensure_dir_exists
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.pybiscus_logger as logm

# -------------------------------------------------------------------------

class ConfigModelWeightVignetteDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    reporting_sub_dir: str = "rounds"
    layers_sub_dir: str = "layers"
    layer_prefix: str = "layer"
    
    mode_bias_values: bool = True
    mode_layers_values: bool = True
    max_filters: int = 8

    webhook_url: str = "http://localhost:5555/webhook/vignettes"

    debug: bool = False

    model_config = ConfigDict(extra="forbid")


class ConfigModelWeightVignetteStrategyDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "VisualizeModelLayers"
    name: Literal["visualizemodellayers"]

    config: ConfigModelWeightVignetteDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class ModelWeightVignetteStrategyDecorator(StrategyDecorator):
    """
    Decorator that produces model vignettes.
    """
    
    def __init__(
        self,
        base_strategy: Strategy,
        conf,
    ):
        self.base_strategy = base_strategy
        self.conf = conf

        import pybiscus.core.pybiscuscontext as pcpc
        self.reporting_path = pcpc.pybiscus_context["reporting_path"]

    # -------------------------------------------------------------------------

    def aggregate_fit(self, rnd, results, failures):
        aggregated, _ = super().aggregate_fit(rnd, results, failures)

        if self.conf.debug:
            logm.console.log(f"Model weights Round={rnd}")

        # --- Global model = aggregated weights ---
        server_weights = fl.common.parameters_to_ndarrays(aggregated)
        if self.conf.debug:
            for i, w in enumerate(server_weights):
                logm.console.log(f"  [Global] Layer {i}: shape={w.shape}, size={w.size}")

        # --- Clients weights ---
        client_weights_list = [
            fl.common.parameters_to_ndarrays(fit_res.parameters)
            for _, fit_res in results
        ]

        # client_weights_list : List[List[np.ndarray]]

        if self.conf.debug:
            for client_id, weights in enumerate(client_weights_list):
                for layer_id, w in enumerate(weights):
                    logm.console.log(
                        f"  [Client {client_id}] Layer {layer_id}: shape={w.shape}, size={w.size}"
                    )


        layers_path = self.reporting_path / self.conf.reporting_sub_dir / f"round_{rnd}" / self.conf.layers_sub_dir 
        ensure_dir_exists(layers_path)

        visualize_federated_layers(
            server_weights,
            client_weights_list,
            mode_bias = "values" if self.conf.mode_bias_values else "diff",     # "values" or "diff"
            mode_layers = "values" if self.conf.mode_layers_values else "diff",     # "values" or "diff"
            max_filters = self.conf.max_filters,          # max filters nb display for conv
            save_path = layers_path,
            layer_prefix=self.conf.layer_prefix,
            col = rnd - 1,
            url=self.conf.webhook_url
        )

        return aggregated, {}

def flatten_weights(weights_list):
    """flatten weights to a 1D vector"""
    flat = np.concatenate([w.flatten() for w in weights_list])
    return flat

def weights_to_image(flat_weights, client_id, save_path="./"):

    # Normalisation des valeurs entre 0 et 1
    # values normalization into [0,1]
    normalized = (flat_weights - np.min(flat_weights)) / (np.max(flat_weights) - np.min(flat_weights) + 1e-8)
    
    # squared image size computation
    size = int(np.ceil(np.sqrt(len(normalized))))
    padded = np.zeros(size * size)
    padded[:len(normalized)] = normalized
    image = padded.reshape((size, size))
    
    # print and save
    plt.imshow(image, cmap='viridis')
    plt.axis('off')
    plt.title(f"Client {client_id}")
    plt.savefig(f"{save_path}/client_{client_id}_hash.png", bbox_inches='tight', pad_inches=0)
    plt.close()


# ----------------------------------
# Function handling conv / FC / bias
# ----------------------------------
def plot_layer_comparison(server_layer, client_layers, layer_id, save_path, file_prefix):
    """
    Display server and clients differences on a single line
    """
    n_clients = len(client_layers)
    total_rows = n_clients + 1

    # layer type determination
    layer_type = "Unknown"
    if server_layer.ndim == 4:
        layer_type = "Conv"
    elif server_layer.ndim == 2:
        layer_type = "FC"
    elif server_layer.ndim == 1:
        layer_type = "Bias"

    fig, axes = plt.subplots(total_rows, 1, figsize=(12, 2*total_rows))

    # --- Line 0 = server ---
    ax = axes[0] if total_rows > 1 else axes
    if server_layer.ndim == 4:
        out_c = min(server_layer.shape[0], 12)
        # first canal filters horizontal concatenation
        img = np.hstack([server_layer[i,0,:,:] for i in range(out_c)])
        ax.imshow(img, cmap="coolwarm")
    elif server_layer.ndim == 2:
        sns.heatmap(server_layer, cmap="coolwarm", center=0, ax=ax)
    elif server_layer.ndim == 1:
        ax.bar(range(server_layer.size), server_layer)
    ax.set_title(f"Global Layer {layer_id} ({layer_type})")

    # --- following lines = clients diff ---
    for idx, cl in enumerate(client_layers):
        diff = cl - server_layer
        ax = axes[idx+1] if total_rows > 1 else axes
        if diff.ndim == 4:
            out_c = min(diff.shape[0], 12)
            img = np.hstack([diff[i,0,:,:] for i in range(out_c)])
            ax.imshow(img, cmap="coolwarm", vmin=-np.max(np.abs(diff)), vmax=np.max(np.abs(diff)))
        elif diff.ndim == 2:
            sns.heatmap(diff, cmap="coolwarm", center=0, ax=ax)
        elif diff.ndim == 1:
            ax.bar(range(diff.size), diff)
        ax.set_title(f"Diff Client {idx} - Layer {layer_id}")

    plt.tight_layout()
    # plt.show()
    plt.savefig(f"{save_path}/{file_prefix}_{layer_id}.png", bbox_inches='tight', pad_inches=0)
    plt.close()


# -------------------------------
# main function for whole model 
# -------------------------------
def visualize_model_and_diffs_compact(server_weights, client_weights_list, save_path, layer_prefix):
    for layer_id, sw in enumerate(server_weights):
        client_layers = [cw[layer_id] for cw in client_weights_list]
        plot_layer_comparison(sw, client_layers, layer_id, save_path, layer_prefix)



def visualize_weights_and_differences(server_weights, client_weights_list, save_path, max_filters=8):
    """
    Mixed visualisation :
    - Heatmaps of client/global differences for Conv and FC.
    - Bars for biases.
    """
    n_layers = len(server_weights)
    n_clients = len(client_weights_list)

    for i, w in enumerate(server_weights):

        plt.figure(figsize=(12, 3 * n_clients))

        if w.ndim == 1:
            # --- BIAIS ---
            plt.title(f"Layer {i} (Bias) — Comparison Global vs Clients")
            plt.plot(w, "ko-", label="Global", linewidth=2)
            for c_idx, client_w in enumerate(client_weights_list):
                plt.plot(client_w[i], "x--", label=f"Client {c_idx}")
            plt.legend()
            plt.xlabel("Biais index")
            plt.ylabel("Value")
            plt.grid(alpha=0.3)

        else:
            # --- CONV / FC Layers---
            plt.suptitle(f"Layer {i} — Client vs Global differences", fontsize=14)
            for c_idx, client_w in enumerate(client_weights_list):
                diff = client_w[i] - w

                # Réduction pour affichage lisible
                if diff.ndim == 4:
                    # Convolution — on affiche quelques filtres concaténés
                    out_c = min(diff.shape[0], max_filters)
                    img = np.hstack([diff[j, 0, :, :] for j in range(out_c)])
                elif diff.ndim == 2:
                    img = diff
                else:
                    img = diff.reshape(1, -1)

                ax = plt.subplot(1, n_clients, c_idx + 1)
                sns.heatmap(img, cmap="coolwarm", center=0, ax=ax, cbar=False)
                ax.set_title(f"Client {c_idx}")
                ax.axis("off")

        plt.tight_layout()
        # plt.show()
        plt.savefig(f"{save_path}/layer_{i}.png", bbox_inches='tight', pad_inches=0)


def visualize_federated_layers(
    server_weights,
    client_weights_list,
    mode_bias: str = "values",     # "values" or "diff"
    mode_layers: str = "diff",     # "values" or "diff"
    max_filters: int = 8,          # max filters nb for conv
    save_path: str = None,          # optional saved file path
    layer_prefix: str = "",
    col: int = 0,
    url: str = ""
):
    """
    Federated learning layers visualization
    
    Arguments :
    ----------
    - server_weights : global weights list (np.ndarray)
    - client_weights_list : clients weights list (np.ndarray)
    - mode_bias : "values" for displaying global + clients biases,
                  "diff" for displaying client - global differences
    - mode_layers : "values" for displaying raw vlues heatmaps
                    "diff" for displaying client - global differences
    - max_filters : max filter nb for conv layer
    - save_path : if not None, perform fiel saving instead of plt.show()
    """
    
    n_layers = len(server_weights)
    n_clients = len(client_weights_list)

    for i, sw in enumerate(server_weights):

        is_bias = (sw.ndim == 1)

        # --- biases ---
        if is_bias:
            plt.figure(figsize=(8, 4))
            if mode_bias == "values":
                plt.title(f"Layer {i} (Bias) - Global and clients values")
                plt.plot(sw, "ko-", label="Global", linewidth=2)
                for j, cw in enumerate(client_weights_list):
                    plt.plot(cw[i], "x--", label=f"Client {j}", alpha=0.7)
            else:  # diff
                plt.title(f"Layer {i} (Bias) - Difference clients vs global")
                for j, cw in enumerate(client_weights_list):
                    diff = cw[i] - sw
                    plt.plot(diff, "x--", label=f"Client {j}", alpha=0.7)
                plt.axhline(0, color="black", linewidth=1)
            plt.xlabel("Bias Index")
            plt.ylabel("Value")
            plt.legend()
            plt.grid(alpha=0.3)
            plt.tight_layout()

        else:
            # --- non-bias layers ---
            n_cols = n_clients + 1
            plt.figure(figsize=(3*n_cols, 3))
            plt.suptitle(f"Layer {i} - {'Diffs' if mode_layers=='diff' else 'Values'}", fontsize=13)

            # Affichage global (colonne 0)
            ax = plt.subplot(1, n_cols, 1)
            if sw.ndim == 4:  # convolution
                out_c = min(sw.shape[0], max_filters)
                img = np.hstack([sw[k, 0, :, :] for k in range(out_c)])
            else:
                img = sw
            sns.heatmap(img, cmap="viridis", ax=ax)
            ax.set_title("Global")
            ax.axis("off")

            # Affichage clients
            for j, cw in enumerate(client_weights_list):
                ax = plt.subplot(1, n_cols, j + 2)
                if mode_layers == "diff":
                    diff = cw[i] - sw
                    if diff.ndim == 4:
                        out_c = min(diff.shape[0], max_filters)
                        img = np.hstack([diff[k, 0, :, :] for k in range(out_c)])
                    else:
                        img = diff
                    sns.heatmap(img, cmap="coolwarm", center=0, ax=ax, cbar=False)
                    ax.set_title(f"Client {j}\n(diff)")
                else:  # valeurs brutes
                    val = cw[i]
                    if val.ndim == 4:
                        out_c = min(val.shape[0], max_filters)
                        img = np.hstack([val[k, 0, :, :] for k in range(out_c)])
                    else:
                        img = val
                    sns.heatmap(img, cmap="viridis", ax=ax, cbar=False)
                    ax.set_title(f"Client {j}\n(values)")
                ax.axis("off")

            plt.tight_layout(rect=[0, 0, 1, 0.9])
        
        if save_path:

            layer_img_path = f"{save_path}/{layer_prefix}_{i}.png"
            plt.savefig(layer_img_path, bbox_inches='tight')
            plt.close()

            import requests
            import json

            payload = {
                "col": col,
                "row": i,
            }

            # logm.console.log(f"**** sending vignette ${payload}")

            with open(layer_img_path, "rb") as f:
                files = {"file": f}
                data = {"metadata": json.dumps(payload)}

                response = requests.post(url, files=files, data=data)

                # logm.console.log(response)
                # print(response.json())

        else:
            plt.show()
