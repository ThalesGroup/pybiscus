from typing import ClassVar, List, Literal, Tuple, Any

import numpy as np
from pydantic import BaseModel, ConfigDict
import torch
from collections import OrderedDict

import flwr as fl
from flwr.common import Parameters

from flwr.server.strategy import Strategy
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
import flwr as fl
from flwr.common import Parameters, parameters_to_ndarrays

from pybiscus.interfaces.flower.strategydecorator import StrategyDecorator
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory
from pybiscus.core.ensure_filesystem import ensure_file_dir_exists, ensure_dir_exists
import pybiscus.core.pybiscus_logger as logm


from tqdm import tqdm
from torch.utils.data import DataLoader
import pandas as pd


def print_GPU_usage(suffix=""):
    device = torch.device('cuda:0')
    free, total = torch.cuda.mem_get_info(device)
    mem_used_MB = (total - free) / 1024 ** 2
    print("GPU usage", mem_used_MB, suffix)

# --------------------------------------------------------
    
class ConfigFedMIAPrivacyEvaluationStrategyDecoratorData(BaseModel):

    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    reporting_sub_dir: str = "rounds"
    cosine_matrix_path: str = "cosine_matrix.csv"
    losses_path: str = "loss_per_instances.csv"
    # model_ids_path : str = "models_ids_list.txt"
    # data_ids_path : str = "data_ids_list.txt"
    criterion: str = "CrossEntropyLoss"
    server_aggregated_fit_parameters_file_name: str = "server_aggregated_fit_parameters.npz"
    client_fitin_parameters_file_prefix: str = "client_fitin_parameters"
    client_fitres_parameters_file_prefix: str = "client_fitres_parameters"
    # parameters_iterator : Iterator[Parameter] = None
    # Todo fournir plutot un fichier avec la liste
    device: str="cuda"

    model_config = ConfigDict(extra="forbid")

class ConfigFedMIAPrivacyEvaluationStrategyDecorator(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "FedMIAPrivacyEvaluation"
    name:   Literal["fedmiaprivacyevaluation"]

    config: ConfigFedMIAPrivacyEvaluationStrategyDecoratorData

    model_config = ConfigDict(extra="forbid")


class FedMIAPrivacyEvaluationStrategyDecorator(StrategyDecorator):
    """
    Decorator that save all the base strategy clients fit in params
    useful when each client is given a dedicated value
    otherwise the servet fit params fit
    """
    
    def __init__(
        self,
        base_strategy: Strategy,
        pybiscus_strategy: FabricStrategyFactory,
        config : ConfigFedMIAPrivacyEvaluationStrategyDecorator
        
        
    ):
        """
        Args:
            base_strategy: the base strategy to decorate
            result_modifier: configuration of the result modifier
        """
        self.base_strategy = base_strategy
        self.model = pybiscus_strategy.model
        self.state_dict = self.model.state_dict()
        # Todo permettre de lister les parametres
        self.parameters_iterator = self.model.parameters()
        if hasattr(pybiscus_strategy, 'privacyset'):
            self.privacyset = pybiscus_strategy.privacyset
        else:
            self.privacyset = None
        if self.privacyset is None:
            logm.console.log("No privacyset defined in the strategy, cannot perform the Privacy Evaluation")
        self.fabric = pybiscus_strategy.fabric
        self.criterion = self._make_loss(config.criterion)
        self.conf = config

        
        

    # -------------------------------------------------------------------------
    def forward_train(self, x, target):
        # Some model compute losses only in train mode
        self.model.train()
        res = self.model(x, target)
        return res

    def _make_loss(self, name, **kwargs):
        if name=="model_val":
            return self.forward_train 
        elif not hasattr(torch.nn, name):
            raise ValueError(f'No torch.nn loss named: {name}')
        else:
            cls = getattr(torch.nn, name)
        return cls(**kwargs)

    def configure_fit(
        self,
        server_round: int,
        parameters: Parameters,
        client_manager: ClientManager,
    ) -> List[Tuple[ClientProxy, fl.common.FitIns]]:
        """send personalized models to clients"""

        import pybiscus.core.pybiscuscontext as pcpc
        self.reporting_path = pcpc.pybiscus_context["reporting_path"]

        if self.model is None:
            self.fabric = pcpc.pybiscus_context["fabric"]
            self.model = pcpc.pybiscus_context["model"]
            self.state_dict = self.model.state_dict()
            if self.parameters_iterator is None:
                self.parameters_iterator = self.model.parameters()

        # get base config
        base_config = self.base_strategy.configure_fit( server_round, parameters, client_manager )
        
        global_weights = fl.common.parameters_to_ndarrays(parameters)

        round_path = self.reporting_path / self.conf.reporting_sub_dir
        ensure_dir_exists(round_path)
        params_path = round_path / f"round_{server_round}" / self.conf.server_aggregated_fit_parameters_file_name
        ensure_file_dir_exists(params_path)
        np.savez(params_path, *global_weights)
        
        for client_proxy, fit_ins in base_config:

            client_weights = parameters_to_ndarrays(fit_ins.parameters)

            cid = client_proxy.cid
            params_path = round_path / f"round_{server_round}" / f"{self.conf.client_fitin_parameters_file_prefix}_{cid}.npz"
            ensure_file_dir_exists(params_path)
            np.savez(params_path, *client_weights)


        return base_config
    
    def aggregate_fit(self, server_round, results, failures):

        aggregated, _ = super().aggregate_fit(server_round, results, failures)
        round_path = self.reporting_path / self.conf.reporting_sub_dir
        ensure_dir_exists(round_path)
        cid_list = []
        for client_proxy, fit_res in results:

            cid = client_proxy.cid
            cid_list.append(cid)
            logm.console.log(f"Source is flower => client_id = {cid}")
            logm.console.log(f"Source is metrics => cid = {fit_res.metrics['cid']}")

            result_path = round_path / f"round_{server_round}" / f"{self.conf.client_fitres_parameters_file_prefix}_{cid}.npz"

            result = fl.common.parameters_to_ndarrays(fit_res.parameters)

            np.savez(result_path, *result)
        
        if server_round>=1 :
            if self.privacyset is not None:
                self._process_client_round(
                    round_num= server_round,
                    cid_list= cid_list,
                    MIADataloader = self.privacyset,
                    criterion = self.criterion,
                    device= self.conf.device)
            else:
                logm.console.log("No privacyset defined in the strategy, cannot perform the Privacy Evaluation")

        return aggregated, {}

    def _compute_per_instance_losses(self, state_dict, dataloader, criterion, device="cuda"):
        """
        Compute gradients for each sample in the batch x.
        Args:
            state_dict: state_dict.
            dataloader: DataLoader for the dataset
            criterion: Loss function.
            device: Device to use.
        Returns:
            loss_per_instance: List of length N, the number of instances in dataloader.
        """
        self.model.load_state_dict(state_dict)
        # self.model.to(device)
        self.model.eval()
        self.model.zero_grad()
        loss_per_instance =[]
        for x, y in tqdm(dataloader):
            # x, y = x.to(device), y.to(device)
            # Compute per-instance loss for the batch
            B = x.shape[0]

            if self.conf.criterion!="model_val":
                output = self.model(x)
            for i in range(B):
                # Compute loss for the i-th sample
                if self.conf.criterion!="model_val":
                    loss_i = criterion(output[i:i+1], y[i:i+1])
                elif isinstance(y, dict):
                    y_i={}
                    for k,v in y.items():
                        if isinstance(v, torch.Tensor):
                            y_i[k]=v[i]
                        else:
                            y_i[k]=[v[i]]
                    loss_i = criterion(x[i:i+1], [y_i])
                else:
                    loss_i = criterion(x[i:i+1], y[i:i+1])

                self.model.zero_grad(set_to_none=True)
                if isinstance(loss_i, dict):
                    loss_i = sum(loss.detach().cpu().item() for loss in loss_i.values())
                    loss_per_instance.append(loss_i)
                else:
                    loss_per_instance.append(loss_i.detach().cpu().item())

        return loss_per_instance  # Len nb_data


    def _compute_per_instance_gradients(self, x, y, criterion):
        """
        Compute gradients for each sample in the batch x.
        Args:
            x: Input batch tensor of shape (B, ...).
            y: Target batch tensor of shape (B,).
            criterion: Loss function.
            device: Device to use.
        Returns:
            grads_per_instance: Tensor of shape (B, P), where P is the total number of parameters.
        """
        B = x.shape[0]
        self.model.eval()
        self.model.zero_grad()
           
        if self.conf.criterion!="model_val":
            output = self.model(x)
        # Compute gradients for each sample in the batch
        grads_per_instance = []
        loss_per_instance =[]
        for i in range(B):
            # Compute loss for the i-th sample
            if self.conf.criterion!="model_val":
                loss_i = criterion(output[i:i+1], y[i:i+1])
            elif isinstance(y, dict):
                y_i={}
                for k,v in y.items():
                    if isinstance(v, torch.Tensor):
                        y_i[k]=v[i]
                    else:
                        y_i[k]=[v[i]]
                loss_i = criterion(x[i:i+1], [y_i])
            else:
                loss_i = criterion(x[i:i+1], y[i:i+1])
            # Zero gradients for this iteration
            self.model.zero_grad(set_to_none=True)
            if isinstance(loss_i, dict):
                loss_i = sum(loss for loss in loss_i.values())
            loss_per_instance.append(loss_i.item())
            # Backward pass for the i-th sample
            loss_i.backward(retain_graph=True if i < B-1 else False)
            # Flatten and save gradients
            grad_flat = torch.cat([
                p.grad.flatten() if (p.grad is not None) 
                else torch.zeros(p.shape, device=p.device).flatten() 
                for _, p in self.model.named_parameters() 
            ])
            grads_per_instance.append(grad_flat)

        return torch.stack(grads_per_instance), loss_per_instance  # Shape: (B, P), len B


    def _compute_cosine_similarity_matrix(self, server_state_dict, dataloader, clients_updates, criterion, device="cuda"):
        """
        Compute cosine similarity between gradients of each data point and gradients_L.
        Args:
            dataloader: DataLoader for the dataset.
            clients_updates: Updates of each clients stored in a tensor (nb_clients, nb_parameters).
            criterion: Loss function.
            device: Device to use.
        Returns:
            cosine_sim_matrix: Tensor of shape (nb_data, nb_clients).
            total_loss_per_instance: List of loss per instance, nb_data length
        """
        self.model.load_state_dict(server_state_dict)
        # self.model.to(device)
        clients_updates = clients_updates.to(device)
        cosine_sim_matrix = []

        # Normalize clients_updates once
        clients_updates_norm = clients_updates / (clients_updates.norm(dim=1, keepdim=True) + 1e-8)
        total_loss_per_instance = []
        for x, y in tqdm(dataloader):
            # x, y = x.to(device), y.to(device)
            # Compute per-instance gradients for the batch
            grads_per_instance, loss_per_instance = self._compute_per_instance_gradients(x, y, criterion)
            # Normalize per-instance gradients
            grads_per_instance_norm = grads_per_instance / (grads_per_instance.norm(dim=1, keepdim=True) + 1e-8)
            grads_per_instance_norm = grads_per_instance_norm.to(device)
            # Compute cosine similarity: (B, P) @ (P, L).T = (B, L)
            cosine_sim = torch.mm(-grads_per_instance_norm, clients_updates_norm.T)
            cosine_sim_matrix.append(cosine_sim)
            total_loss_per_instance.extend(loss_per_instance)
        return torch.cat(cosine_sim_matrix, dim=0), total_loss_per_instance

    def _from_npz_to_state_dict(self, npz_path):
        if self.model==None:
            return None
        npz_data = np.load(npz_path)
        nparray_list = [npz_data[ndarray] for ndarray in npz_data]
        state_dict = OrderedDict({
            k: torch.tensor(v)
            for k,v in zip(self.state_dict.keys(), nparray_list)
        })
        return state_dict

    def _process_client_round(
        self,
        round_num: int,
        cid_list: list[int],
        MIADataloader: torch.utils.data.DataLoader,
        criterion,
        device
    ) -> list[dict[str, Any]]:

        
        MIADataset = MIADataloader.dataset
        MIAindices = [i for i in range(len(MIADataset))]
        if hasattr(MIADataset, 'indices'):
            MIAindices = MIADataset.indices

        batch_size = MIADataloader.batch_size

        MIADataloader = self.fabric._setup_dataloader(
            DataLoader( MIADataset,  batch_size=batch_size, num_workers=8, drop_last=False, shuffle=False))

        round_path = self.reporting_path / self.conf.reporting_sub_dir
        ensure_dir_exists(round_path)

        server_params_path = round_path / f"round_{round_num}" / self.conf.server_aggregated_fit_parameters_file_name
        ensure_file_dir_exists(server_params_path)
        server_state_dict = self._from_npz_to_state_dict(server_params_path)

        clients_updates = []
        clients_res_losses = []
        clients_in_losses = []
        for cid in cid_list: # alternative, take into account all files found
            client_in_params_path = round_path / f"round_{round_num}" / f"{self.conf.client_fitin_parameters_file_prefix}_{cid}.npz"
            ensure_file_dir_exists(client_in_params_path)
            client_in_state_dict = self._from_npz_to_state_dict(client_in_params_path)
            client_res_params_path = round_path / f"round_{round_num}" / f"{self.conf.client_fitres_parameters_file_prefix}_{cid}.npz"
            ensure_file_dir_exists(client_res_params_path)
            client_res_state_dict = self._from_npz_to_state_dict(client_res_params_path)

            clients_res_losses.append(
                self._compute_per_instance_losses(
                    state_dict=client_res_state_dict,
                    dataloader=MIADataloader,
                    criterion=criterion,
                    device=device
                ))
            clients_in_losses.append(
                self._compute_per_instance_losses(
                    state_dict=client_in_state_dict,
                    dataloader=MIADataloader,
                    criterion=criterion,
                    device=device
                ))
            # Δw par clé de paramètre
            client_update = []
            for k, _ in self.model.named_parameters():
                key = f"model.{k.partition('model.')[2]}"
                client_update.append(
                    torch.tensor(np.asarray(client_res_state_dict[key], dtype=np.float32) 
                                 - np.asarray(client_in_state_dict[key], dtype=np.float32))
                                 .flatten()
                )
            clients_updates.append(torch.cat(client_update).flatten().unsqueeze(0))
        logm.console.log(cid_list, len(clients_updates))
        clients_updates_tensor = torch.cat(clients_updates) # Shape : (nb_clients, nb_parameters)
        logm.console.log(clients_updates_tensor.shape)
        cosine_matrix, server_losses= self._compute_cosine_similarity_matrix(
            server_state_dict=server_state_dict,
            dataloader=MIADataloader,
            clients_updates=clients_updates_tensor,
            criterion=criterion,
            device=device
        )
        # Cosine_matrix (nb_data,nb_clients), server_losses is of length nb_data
        logm.console.log("done", cosine_matrix.shape, len(server_losses))
        data_matrix = {cid_client : cosine_matrix[:,i].tolist() for i, cid_client in enumerate(cid_list)}
        df_matrix = pd.DataFrame(data=data_matrix, index=MIAindices)
        df_matrix.to_csv(f"{round_path}/round_{round_num}/{self.conf.cosine_matrix_path}", index_label='Image_idx')

        data_losses = {f"{cid_client}_in" : clients_in_losses[i] for i, cid_client in enumerate(cid_list)}
        for i, cid_client in enumerate(cid_list):
            data_losses[f"{cid_client}_res"] = clients_res_losses[i]
        data_losses["server_in"] = server_losses
        df_losses = pd.DataFrame(data=data_losses, index=MIAindices)
        df_losses.to_csv(f"{round_path}/round_{round_num}/{self.conf.losses_path}", index_label='Image_idx')
        return None



