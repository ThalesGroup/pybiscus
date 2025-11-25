import torch
import numpy as np
from collections import OrderedDict
import argparse

def replace_checkpoint_weights_safe(ckpt_path: str, weights_path: str, output_path: str):
    """
    Remplace les poids dans un checkpoint PyTorch/Lightning par ceux d'un dump numpy,
    en vérifiant que les dimensions correspondent.
    
    Args:
        ckpt_path (str): chemin vers le checkpoint existant (.pt ou .ckpt)
        weights_path (str): chemin vers le fichier numpy (.npz)
        output_path (str): chemin pour sauvegarder le nouveau checkpoint
    """
    # 1️⃣ Charger le checkpoint existant
    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=True)

    # old_state_dict = checkpoint['state_dict']

    # Détecter correctement le state_dict
    if "state_dict" in checkpoint:
        old_state_dict = checkpoint["state_dict"]
    elif "model" in checkpoint:
        old_state_dict = checkpoint["model"]
    else:
        raise ValueError("Checkpoint inattendu, pas de 'state_dict' ni 'model' trouvé")


    # 2️⃣ Charger le dump numpy
    data = np.load(weights_path)
    params = [data[f"arr_{i}"] for i in range(len(data.files))]

    if len(params) != len(old_state_dict):
        raise ValueError(f"Nombre de poids dans le dump ({len(params)}) "
                         f"ne correspond pas au nombre de paramètres du checkpoint ({len(old_state_dict)})")

    # 3️⃣ Remplacer les poids en vérifiant la forme
    new_state_dict = OrderedDict()
    for (key, old_tensor), new_val in zip(old_state_dict.items(), params):
        if old_tensor.shape != new_val.shape:
            raise ValueError(f"Forme incompatible pour '{key}': "
                             f"checkpoint {tuple(old_tensor.shape)} vs numpy {new_val.shape}")
        new_state_dict[key] = torch.tensor(new_val, dtype=old_tensor.dtype)
        print(f"✅ {key} remplacé")

    checkpoint['state_dict'] = new_state_dict

    # 4️⃣ Sauvegarder le nouveau checkpoint
    torch.save(checkpoint, output_path)
    print(f"✅ Nouveau checkpoint créé : {output_path}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Remplacer les poids d'un checkpoint PyTorch/Lightning par un dump numpy (vérification des formes)")
    parser.add_argument("--checkpoint", type=str, required=True, help="Chemin vers le checkpoint existant (.pt/.ckpt)")
    parser.add_argument("--weights", type=str, required=True, help="Chemin vers le fichier numpy contenant les poids (.npz)")
    parser.add_argument("--output", type=str, required=True, help="Chemin pour sauvegarder le nouveau checkpoint")
    
    args = parser.parse_args()
    
    replace_checkpoint_weights_safe(args.checkpoint, args.weights, args.output)
