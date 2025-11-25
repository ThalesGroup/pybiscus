from pathlib import Path
import numpy as np
import torch

from pybiscus.commands.app_server import check_and_build_server_config
from pybiscus.commands.apps_common import load_config
from pybiscus.flower.utils_server import get_params, set_params
from pybiscus.plugin.registries.model_registry import model_registry
# from pybiscus.plugins_of_app.pybiscusplugins import get_plugins_by_category

def npz2cp( model_path, config_path, weights_path ):

    # plugins_by_category = get_plugins_by_category()

    config = Path(config_path)

    conf_loaded = load_config(config)

    params = np.load(weights_path)

    conf = check_and_build_server_config(conf_loaded)

    # load the model
    model_class = model_registry()[conf.model.name]
    _model = model_class(**conf.model.config.model_dump())


    # print(params.files)  # noms des tableaux contenus
    # print(len(params.files))

    # for k in params.files:
    #     print(k, params[k].dtype, params[k].shape)

    # Convertir en liste de tableaux
    params_list = [params[k] for k in params.files]

    set_params(_model, params_list)

    # Doit afficher True
    print(len(get_params(_model)) == len(params))

    torch.save(_model.state_dict(), model_path)

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description="Inject npz weights into a PyTorch/Lightning model")
    
    parser.add_argument(
        "--model-path",
        type=str,
        required=True,
        help="Path where the model/checkpoint will be saved"
    )

    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the config_server.yml file"
    )

    parser.add_argument(
        "--weights-path",
        type=str,
        required=True,
        help="Path to the .npz weights file"
    )

    args = parser.parse_args()
    
    npz2cp(args.model_path, args.config, args.weights_path)
