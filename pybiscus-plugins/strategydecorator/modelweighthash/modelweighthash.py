from pathlib import Path
from typing import ClassVar, List, Literal, Tuple, Optional, Dict
import flwr as fl
from flwr.common import (
    Parameters, 
)

from flwr.server.strategy import Strategy
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy

import numpy as np
from pydantic import BaseModel, ConfigDict
import matplotlib.pyplot as plt
import seaborn as sns



from pybiscus.core.ensure_filesystem import ensure_file_dir_exists, ensure_dir_exists
from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
import pybiscus.core.pybiscus_logger as logm

# -------------------------------------------------------------------------

class ConfigModelWeightHashDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    mode_bias_values: bool = True
    mode_layers_values: bool = True
    max_filters: int = 8

    model_config = ConfigDict(extra="forbid")


class ConfigModelWeightHashStrategyDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "ModelWeightHash"
    name: Literal["modelweighthash"]

    config: ConfigModelWeightHashDecoratorData

    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------------

class ModelWeighthashStrategyDecorator(StrategyDecorator):
    """
    Decorator that add result personalization to a Flower strategy.
    """
    
    def __init__(
        self,
        base_strategy: Strategy,
        conf,
    ):
        """
        Args:
            base_strategy: the base strategy to decorate
            result_modifier: configuration of the result modifier
        """
        self.base_strategy = base_strategy
        self.conf = conf

        import pybiscus.core.pybiscuscontext as pcpc
        self.reporting_path = pcpc.pybiscus_context["reporting_path"]

    # -------------------------------------------------------------------------

    def aggregate_fit(self, rnd, results, failures):
        """
        [🖧] Model weights Round=9
        [🖧] [Global] Layer 0: shape=(5,), size=5
        [🖧] [Client 0] Layer 0: shape=(5,), size=5
        [🖧] [Client 1] Layer 0: shape=(5,), size=5

2025-11-10 14:45:40,246 - Model weights Round=10

   [Global] Layer 0: shape=(6, 3, 5, 5), size=450
   [Global] Layer 1: shape=(6,), size=6
   [Global] Layer 2: shape=(16, 6, 5, 5), size=2400
   [Global] Layer 3: shape=(16,), size=16
   [Global] Layer 4: shape=(120, 400), size=48000
   [Global] Layer 5: shape=(120,), size=120
   [Global] Layer 6: shape=(84, 120), size=10080
   [Global] Layer 7: shape=(84,), size=84
   [Global] Layer 8: shape=(10, 84), size=840
   [Global] Layer 9: shape=(10,), size=10

2025-11-10 14:45:40,266 -   [Client 0] Layer 0: shape=(6, 3, 5, 5), size=450
2025-11-10 14:45:40,267 -   [Client 0] Layer 1: shape=(6,), size=6
2025-11-10 14:45:40,270 -   [Client 0] Layer 2: shape=(16, 6, 5, 5), size=2400
2025-11-10 14:45:40,272 -   [Client 0] Layer 3: shape=(16,), size=16
2025-11-10 14:45:40,274 -   [Client 0] Layer 4: shape=(120, 400), size=48000
2025-11-10 14:45:40,276 -   [Client 0] Layer 5: shape=(120,), size=120
2025-11-10 14:45:40,278 -   [Client 0] Layer 6: shape=(84, 120), size=10080
2025-11-10 14:45:40,280 -   [Client 0] Layer 7: shape=(84,), size=84
2025-11-10 14:45:40,282 -   [Client 0] Layer 8: shape=(10, 84), size=840
2025-11-10 14:45:40,284 -   [Client 0] Layer 9: shape=(10,), size=10

2025-11-10 14:45:40,285 -   [Client 1] Layer 0: shape=(6, 3, 5, 5), size=450
2025-11-10 14:45:40,287 -   [Client 1] Layer 1: shape=(6,), size=6
2025-11-10 14:45:40,289 -   [Client 1] Layer 2: shape=(16, 6, 5, 5), size=2400
2025-11-10 14:45:40,291 -   [Client 1] Layer 3: shape=(16,), size=16
2025-11-10 14:45:40,293 -   [Client 1] Layer 4: shape=(120, 400), size=48000
2025-11-10 14:45:40,294 -   [Client 1] Layer 5: shape=(120,), size=120
2025-11-10 14:45:40,296 -   [Client 1] Layer 6: shape=(84, 120), size=10080
2025-11-10 14:45:40,298 -   [Client 1] Layer 7: shape=(84,), size=84
2025-11-10 14:45:40,299 -   [Client 1] Layer 8: shape=(10, 84), size=840
2025-11-10 14:45:40,301 -   [Client 1] Layer 9: shape=(10,), size=10        
        """

        aggregated, _ = super().aggregate_fit(rnd, results, failures)

        logm.console.log(f"Model weights Round={rnd}")

        # --- Poids agrégés (modèle global) ---
        server_weights = fl.common.parameters_to_ndarrays(aggregated)
        for i, w in enumerate(server_weights):
            logm.console.log(f"  [Global] Layer {i}: shape={w.shape}, size={w.size}")


        # --- Poids des clients ---
        client_weights_list = [
            fl.common.parameters_to_ndarrays(fit_res.parameters)
            for _, fit_res in results
        ]

        # client_weights_list : List[List[np.ndarray]]

        for client_id, weights in enumerate(client_weights_list):
            for layer_id, w in enumerate(weights):
                logm.console.log(
                    f"  [Client {client_id}] Layer {layer_id}: shape={w.shape}, size={w.size}"
                )

        # for i, weights in enumerate(client_weights_list):

        #     for weight in weights:
        #         logm.console.log(f"# client={i} sh={weight.shape} sz={weight.size} ")

            # flat = flatten_weights(weights)

            # logm.console.log(f" flat sh={flat.shape} sz={flat.size} ")

            # weights_to_image(flat, client_id=i, save_path="./hash_images")

        weights_path = self.reporting_path / f"weights/round_{rnd}"
        ensure_dir_exists(weights_path)

        # visualize_model_and_diffs_compact(server_weights, client_weights_list, weights_path)
        # visualize_weights_and_differences(server_weights, client_weights_list, weights_path, max_filters=8)

        visualize_federated_layers(
            server_weights,
            client_weights_list,
            mode_bias = "values" if self.conf.mode_bias_values else "diff",     # "values" ou "diff"
            mode_layers = "values" if self.conf.mode_layers_values else "diff",     # "values" ou "diff"
            max_filters = self.conf.max_filters,          # nombre max de filtres affichés pour conv
            save_path = weights_path          # chemin optionnel pour sauvegarder la figure
        )

        return aggregated, {}

def flatten_weights(weights_list):
    """Concatène tous les poids d'un client en un seul vecteur 1D."""
    flat = np.concatenate([w.flatten() for w in weights_list])
    return flat

def weights_to_image(flat_weights, client_id, save_path="./"):

    # Normalisation des valeurs entre 0 et 1
    normalized = (flat_weights - np.min(flat_weights)) / (np.max(flat_weights) - np.min(flat_weights) + 1e-8)
    
    # Choix d’une taille d’image carrée
    size = int(np.ceil(np.sqrt(len(normalized))))
    padded = np.zeros(size * size)
    padded[:len(normalized)] = normalized
    image = padded.reshape((size, size))
    
    # Affichage et sauvegarde
    plt.imshow(image, cmap='viridis')
    plt.axis('off')
    plt.title(f"Client {client_id}")
    plt.savefig(f"{save_path}/client_{client_id}_hash.png", bbox_inches='tight', pad_inches=0)
    plt.close()


# -------------------------------
# Fonction compacte pour conv / FC / biais
# -------------------------------
def plot_layer_comparison(server_layer, client_layers, layer_id, save_path):
    """
    Affiche le serveur et les différences clients sur une seule figure
    """
    n_clients = len(client_layers)
    total_rows = n_clients + 1

    # Déterminer le type de couche
    layer_type = "Unknown"
    if server_layer.ndim == 4:
        layer_type = "Conv"
    elif server_layer.ndim == 2:
        layer_type = "FC"
    elif server_layer.ndim == 1:
        layer_type = "Bias"

    fig, axes = plt.subplots(total_rows, 1, figsize=(12, 2*total_rows))

    # --- Ligne 0 = serveur ---
    ax = axes[0] if total_rows > 1 else axes
    if server_layer.ndim == 4:
        out_c = min(server_layer.shape[0], 12)
        # concaténation horizontale des filtres du premier canal
        img = np.hstack([server_layer[i,0,:,:] for i in range(out_c)])
        ax.imshow(img, cmap="coolwarm")
    elif server_layer.ndim == 2:
        sns.heatmap(server_layer, cmap="coolwarm", center=0, ax=ax)
    elif server_layer.ndim == 1:
        ax.bar(range(server_layer.size), server_layer)
    ax.set_title(f"Global Layer {layer_id} ({layer_type})")

    # --- Lignes suivantes = diff clients ---
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
    plt.savefig(f"{save_path}/layer_{layer_id}.png", bbox_inches='tight', pad_inches=0)
    plt.close()


# -------------------------------
# Fonction principale pour tout le modèle
# -------------------------------
def visualize_model_and_diffs_compact(server_weights, client_weights_list, save_path):
    for layer_id, sw in enumerate(server_weights):
        client_layers = [cw[layer_id] for cw in client_weights_list]
        plot_layer_comparison(sw, client_layers, layer_id, save_path)



def visualize_weights_and_differences(server_weights, client_weights_list, save_path, max_filters=8):
    """
    Visualisation mixte :
    - Heatmaps de différences client/global pour Conv et FC.
    - Barres pour les biais.
    """
    n_layers = len(server_weights)
    n_clients = len(client_weights_list)

    for i, w in enumerate(server_weights):
        plt.figure(figsize=(12, 3 * n_clients))

        if w.ndim == 1:
            # --- BIAIS ---
            plt.title(f"Layer {i} (Bias) — Comparaison Global vs Clients")
            plt.plot(w, "ko-", label="Global", linewidth=2)
            for c_idx, client_w in enumerate(client_weights_list):
                plt.plot(client_w[i], "x--", label=f"Client {c_idx}")
            plt.legend()
            plt.xlabel("Index du biais")
            plt.ylabel("Valeur")
            plt.grid(alpha=0.3)

        else:
            # --- COUCHES CONV / FC ---
            plt.suptitle(f"Layer {i} — Différences Client vs Global", fontsize=14)
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
    mode_bias: str = "values",     # "values" ou "diff"
    mode_layers: str = "diff",     # "values" ou "diff"
    max_filters: int = 8,          # nombre max de filtres affichés pour conv
    save_path: str = None          # chemin optionnel pour sauvegarder la figure
):
    """
    Visualisation des couches d'un modèle fédéré.
    
    Arguments :
    ----------
    - server_weights : liste des poids globaux (np.ndarray)
    - client_weights_list : liste de listes de poids clients (np.ndarray)
    - mode_bias : "values" pour afficher les biais globaux + clients,
                  "diff" pour afficher les différences client - global
    - mode_layers : "values" pour afficher les heatmaps des valeurs brutes,
                    "diff" pour afficher les différences client - global
    - max_filters : limite du nombre de filtres à afficher pour couches conv
    - save_path : si non None, sauvegarde la figure au lieu de plt.show()
    """
    
    n_layers = len(server_weights)
    n_clients = len(client_weights_list)

    for i, sw in enumerate(server_weights):

        is_bias = (sw.ndim == 1)

        # --- Cas des biais ---
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
            if save_path:
                # plt.savefig(f"{save_path}/layer_{i}_bias.png", bbox_inches='tight')
                plt.savefig(f"{save_path}/layer_{i}.png", bbox_inches='tight')
                plt.close()
            else:
                plt.show()
            continue

        # --- Cas des couches non-biais ---
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
            # plt.savefig(f"{save_path}/layer_{i}_heatmap.png", bbox_inches='tight')

            layer_img_path = f"{save_path}/layer_{i}.png"
            plt.savefig(layer_img_path, bbox_inches='tight')
            plt.close()

            import requests

            #TODO ICI
            url = "http://localhost:5000/upload"
            with open(layer_img_path, "rb") as f:
                files = {"file": f}
                response = requests.post(url, files=files)

                print(response.json())

        else:
            plt.show()

if __name__ == "__main__":

    # -------------------------------
    # Exemple d'utilisation
    # -------------------------------
    # Simuler serveur et clients
    server_weights = [
        np.random.randn(6, 3, 5, 5),
        np.random.randn(6,),
        np.random.randn(16, 6, 5, 5),
        np.random.randn(16,),
        np.random.randn(120, 400),
        np.random.randn(120,),
        np.random.randn(84, 120),
        np.random.randn(84,),
        np.random.randn(10, 84),
        np.random.randn(10,),
    ]

    client_weights_list = [
        [sw + np.random.normal(0, 0.05, size=sw.shape) for sw in server_weights],
        [sw + np.random.normal(0, 0.05, size=sw.shape) for sw in server_weights],
    ]

    # Visualiser tout le modèle
    visualize_model_and_diffs_compact(server_weights, client_weights_list, "./")
