import datetime
import json
import os
from pathlib import Path
import pickle
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, ConfigDict

from pybiscus.interfaces.flower.strategydecoratorwithhooks import StrategyDecoratorWithHooks
from pybiscus.interfaces.flower.fabricstrategyfactory import FabricStrategyFactory
import pybiscus.core.pybiscus_logger as logm

from flwr.common import EvaluateRes, FitRes, Parameters, Scalar
from flwr.server.client_proxy import ClientProxy

# -----------------------------------------------

class ConfigFileWritingDecoratorData(BaseModel):
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"

    # empty_configuration: bool = True
    shared_directory       : str = "/tmp/filewriterdecorator"
    save_individual_results: bool = False

    model_config = ConfigDict(extra="forbid")


class ConfigFileWritingDecorator(BaseModel):
    
    PYBISCUS_ALIAS: ClassVar[str] = "FileWriting"
    name: Literal["filewriting"]

    config: ConfigFileWritingDecoratorData

    model_config = ConfigDict(extra="forbid")

# -----------------------------------------------

class FileWritingDecorator(StrategyDecoratorWithHooks):
    """
    Decorator that uses the hook system to save results to files.
    
    Files created:
    /shared_directory/
    ├── session_X_round_0001_global_params.pkl          # Global parameters
    ├── session_X_round_0001_fit_metrics.json           # Training metrics
    ├── session_X_round_0001_eval_metrics.json          # Federated evaluation metrics  
    ├── session_X_round_0001_centralized_eval.json      # Centralized evaluation
    ├── session_X_round_0001_aggregated_metrics.json    # Aggregated metrics
    └── session_X_round_0001_client_*_results.pkl       # Individual results
    """

    def __init__(self, base_strategy, pybiscus_strategy: FabricStrategyFactory, config: ConfigFileWritingDecoratorData):
        super().__init__(base_strategy)

        # TODO: Get from configuration or context
        self.session_id = 0

        # Configuration
        self.config = config
        self.shared_directory = Path(self.config.shared_directory)
        self.save_individual_results = self.config.save_individual_results

        # Create shared directory
        self.shared_directory.mkdir(parents=True, exist_ok=True)

        self.cleanup_all_sessions()
        
        # REGISTER HOOKS (instead of overriding methods)
        self.add_hook('after_aggregate_fit',      self._save_fit_results)
        self.add_hook('after_aggregate_evaluate', self._save_eval_results)
        self.add_hook('after_evaluate',           self._save_centralized_eval_results)
        
        logm.console.log(f"[FileWritingDecorator] Session writing to {self.shared_directory}")

    def _write_file_safely(self, file_path: Path, data: Any, is_binary: bool = False) -> bool:
        temp_file = file_path.with_suffix(file_path.suffix + '.tmp')
        
        try:
            # whole writing into a temp file
            if is_binary:
                with open(temp_file, 'wb') as f:
                    pickle.dump(data, f)
            else:
                with open(temp_file, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
            
            # atomic rename
            temp_file.rename(file_path)
            return True
            
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()  # cleaning
            return False
    
    def _get_file_path(self, round_num: int, file_type: str, client_id: str = None) -> Path:
        """
        Generate file path based on round and type.
        
        Parameters
        ----------
        round_num : int
            Round number
        file_type : str
            Type of file ('global_params', 'metrics', 'client_results', etc.)
        client_id : str, optional
            Client ID for client-specific files
        
        Returns
        -------
        Path
            Full file path
        """
        if file_type == "global_params":
            filename = f"session_{self.session_id}_round_{round_num:04d}_global_params.pkl"
        elif file_type == "fit_metrics":
            filename = f"session_{self.session_id}_round_{round_num:04d}_fit_metrics.json"
        elif file_type == "eval_metrics":
            filename = f"session_{self.session_id}_round_{round_num:04d}_eval_metrics.json"
        elif file_type == "aggregated_metrics":
            filename = f"session_{self.session_id}_round_{round_num:04d}_aggregated_metrics.json"
        elif file_type == "client_results" and client_id:
            filename = f"session_{self.session_id}_round_{round_num:04d}_client_{client_id}_results.pkl"
        elif file_type == "round_summary":
            filename = f"session_{self.session_id}_round_{round_num:04d}_summary.json"
        elif file_type == "centralized_eval":
            filename = f"session_{self.session_id}_round_{round_num:04d}_centralized_eval.json"
        else:
            raise ValueError(f"Unknown file type: {file_type}")
            
        return self.shared_directory / filename

    def _save_client_results(self, round_num: int, results: List[Tuple[ClientProxy, Union[FitRes, EvaluateRes]]], result_type: str):
        """
        Save individual client results.
        
        Parameters
        ----------
        round_num : int
            Round number
        results : List[Tuple[ClientProxy, Union[FitRes, EvaluateRes]]]
            Client results
        result_type : str
            'fit' or 'evaluate'
        """
        if not self.save_individual_results:
            return
            
        for client_proxy, result in results:
            try:
                # Extraire l'ID du client (ou générer un si pas disponible)
                client_id = getattr(client_proxy, 'cid', str(hash(str(client_proxy))))
                
                # Préparer les données à sauvegarder
                client_data = {
                    "client_id": client_id,
                    "round": round_num,
                    "type": result_type,
                    "num_examples": result.num_examples,
                    "metrics": result.metrics,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
                # Pour les résultats de fit, inclure les paramètres
                if result_type == "fit" and hasattr(result, 'parameters'):
                    # Convertir les paramètres en liste numpy pour la sérialisation
                    if result.parameters:
                        # ❌ ANCIEN :
                        # params_list = [np.array(param) for param in result.parameters.tensors]
                        
                        # ✅ NOUVEAU :
                        params_list = []
                        for param in result.parameters.tensors:
                            if hasattr(param, 'numpy'):
                                params_list.append(param.numpy().astype(np.float32))
                            elif isinstance(param, np.ndarray):
                                params_list.append(param.astype(np.float32))
                            else:
                                params_list.append(np.array(param, dtype=np.float32))                        

                        client_data["parameters"] = params_list
                
                # Pour les résultats d'évaluation, inclure la loss
                if result_type == "evaluate" and hasattr(result, 'loss'):
                    client_data["loss"] = result.loss
                
                # Sauvegarder
                file_path = self._get_file_path(round_num, "client_results", client_id)
                self._write_file_safely(file_path, client_data, is_binary=True)
                
            except Exception as e:
                logm.console.log(f"[FileWritingDecorator] Error saving client {client_proxy} results: {e}")

    def _create_round_summary(self, round_num: int, fit_metrics: Dict[str, Scalar] = None, eval_metrics: Dict[str, Scalar] = None):
        """
        Create a summary file for the round.
        
        Parameters
        ----------
        round_num : int
            Round number
        fit_metrics : Dict[str, Scalar], optional
            Aggregated fit metrics
        eval_metrics : Dict[str, Scalar], optional
            Aggregated evaluation metrics
        """
        # Access base strategy attributes via __getattr__
        try:
            fraction_fit = getattr(self, 'fraction_fit', 'unknown')
            fraction_evaluate = getattr(self, 'fraction_evaluate', 'unknown')
            min_fit_clients = getattr(self, 'min_fit_clients', 'unknown')
            min_evaluate_clients = getattr(self, 'min_evaluate_clients', 'unknown')
            min_available_clients = getattr(self, 'min_available_clients', 'unknown')
        except:
            fraction_fit = fraction_evaluate = min_fit_clients = min_evaluate_clients = min_available_clients = 'unknown'

        summary = {
            "session_id": self.session_id,
            "round": round_num,
            "timestamp": datetime.datetime.now().isoformat(),
            "fit_metrics": fit_metrics or {},
            "eval_metrics": eval_metrics or {},
            "strategy_config": {
                "fraction_fit": fraction_fit,
                "fraction_evaluate": fraction_evaluate,
                "min_fit_clients": min_fit_clients,
                "min_evaluate_clients": min_evaluate_clients,
                "min_available_clients": min_available_clients,
            }
        }
        
        file_path = self._get_file_path(round_num, "round_summary")
        self._write_file_safely(file_path, summary, is_binary=False)

    # ============================================
    # HOOKS METHODS (instead of overriding aggregate_fit/aggregate_evaluate)
    # ============================================

    def _save_fit_results(self, server_round: int, results: List[Tuple[ClientProxy, FitRes]], 
                         failures: List[Union[Tuple[ClientProxy, FitRes], BaseException]], 
                         aggregated_parameters: Optional[Parameters], aggregated_metrics: Dict[str, Scalar]):
        """
        Hook called after aggregate_fit to save results.
        
        This method is called automatically through the hook system.
        """

        print(f"🔥 _save_fit_results CALLED! Round {server_round}")
        print(f"   Parameters: {aggregated_parameters is not None}")
        print(f"   Metrics: {aggregated_metrics is not None}")

        try:
            logm.console.log(f"[FileWritingDecorator] Saving fit results for round {server_round}")
            
            # Enhance metrics with session information
            enhanced_metrics = dict(aggregated_metrics) if aggregated_metrics else {}
            enhanced_metrics.update({
                "session_id": self.session_id,
                "round": server_round,
                "num_clients": len(results),
                "num_failures": len(failures),
                "total_examples": sum([fit_res.num_examples for _, fit_res in results]),
                "timestamp": datetime.datetime.now().isoformat()
            })
            
            # Save global parameters
            if aggregated_parameters is not None:
                # Convert to numpy list for serialization
                # ❌ ANCIEN :
                # params_list = [np.array(param) for param in aggregated_parameters.tensors]
    
                # ✅ NOUVEAU :
                # params_list = []
                # for param in aggregated_parameters.tensors:
                #     if hasattr(param, 'numpy'):
                #         params_list.append(param.numpy().astype(np.float32))
                #     elif isinstance(param, np.ndarray):
                #         params_list.append(param.astype(np.float32))
                #     else:
                #         params_list.append(np.array(param, dtype=np.float32))

                # Utiliser la méthode officielle Flower
                from flwr.common import parameters_to_ndarrays

                # ✅ MÉTHODE RECOMMANDÉE :
                try:
                    params_list = parameters_to_ndarrays(aggregated_parameters)
                    print(f"[DEBUG] Converted {len(params_list)} parameters using Flower utils")
                except Exception as e:
                    print(f"[ERROR] Flower conversion failed: {e}")
                    # Fallback vers votre méthode manuelle

                global_params_file = self._get_file_path(server_round, "global_params")
                self._write_file_safely(global_params_file, params_list, is_binary=True)
                
            # Save aggregation metrics
            fit_metrics_file = self._get_file_path(server_round, "fit_metrics")
            self._write_file_safely(fit_metrics_file, enhanced_metrics, is_binary=False)
            
            # Save individual client results
            self._save_client_results(server_round, results, "fit")
            
            # Log summary
            logm.console.log(f"[FileWritingDecorator] Round {server_round} fit aggregation saved: {len(results)} clients, {enhanced_metrics.get('total_examples', 0)} examples")
            
        except Exception as e:
            logm.console.log(f"[FileWritingDecorator] Error in _save_fit_results: {e}")

    def _save_eval_results(self, server_round: int, results: List[Tuple[ClientProxy, EvaluateRes]], 
                          failures: List[Union[Tuple[ClientProxy, EvaluateRes], BaseException]], 
                          aggregated_loss: Optional[float], aggregated_metrics: Dict[str, Scalar]):
        """
        Hook called after aggregate_evaluate to save results.
        
        This method is called automatically through the hook system.
        """
        try:
            logm.console.log(f"[FileWritingDecorator] Saving evaluation results for round {server_round}")
            
            # Enhance metrics with detailed information
            enhanced_metrics = dict(aggregated_metrics) if aggregated_metrics else {}
            
            # Calculate detailed statistics
            if results:
                losses = [eval_res.loss for _, eval_res in results]
                num_examples = [eval_res.num_examples for _, eval_res in results]
                
                # Calculate statistics on losses
                enhanced_metrics.update({
                    "loss_mean": float(np.mean(losses)),
                    "loss_std": float(np.std(losses)),
                    "loss_min": float(np.min(losses)),
                    "loss_max": float(np.max(losses)),
                    "loss_weighted": aggregated_loss,  # Weighted loss from FedAvg
                })
                
                # Aggregate other metrics (accuracy, etc.)
                if results and results[0][1].metrics:
                    metric_keys = results[0][1].metrics.keys()
                    for key in metric_keys:
                        values = []
                        weights = []
                        for _, eval_res in results:
                            if key in eval_res.metrics and isinstance(eval_res.metrics[key], (int, float)):
                                values.append(eval_res.metrics[key])
                                weights.append(eval_res.num_examples)
                        
                        if values:
                            enhanced_metrics[f"{key}_mean"] = float(np.mean(values))
                            enhanced_metrics[f"{key}_std"] = float(np.std(values))
                            enhanced_metrics[f"{key}_min"] = float(np.min(values))
                            enhanced_metrics[f"{key}_max"] = float(np.max(values))
                            # Weighted average
                            enhanced_metrics[f"{key}_weighted"] = float(np.average(values, weights=weights))
            
            # Add metadata
            enhanced_metrics.update({
                "session_id": self.session_id,
                "round": server_round,
                "num_clients": len(results),
                "num_failures": len(failures),
                "total_examples": sum([eval_res.num_examples for _, eval_res in results]) if results else 0,
                "timestamp": datetime.datetime.now().isoformat()
            })
            
            # Save evaluation metrics
            eval_metrics_file = self._get_file_path(server_round, "eval_metrics")
            self._write_file_safely(eval_metrics_file, enhanced_metrics, is_binary=False)
            
            # Also save as aggregated metrics (for relay client compatibility)
            aggregated_metrics_file = self._get_file_path(server_round, "aggregated_metrics")
            self._write_file_safely(aggregated_metrics_file, enhanced_metrics, is_binary=False)
            
            # Save individual client results
            self._save_client_results(server_round, results, "evaluate")
            
            # Create round summary
            self._create_round_summary(server_round, eval_metrics=enhanced_metrics)
            
            # Log summary
            if aggregated_loss is not None:
                logm.console.log(f"[FileWritingDecorator] Round {server_round} evaluation saved: loss={aggregated_loss:.4f}, {len(results)} clients")
                
        except Exception as e:
            logm.console.log(f"[FileWritingDecorator] Error in _save_eval_results: {e}")

    def _save_centralized_eval_results(self, server_round: int, parameters: Parameters, 
                                     result: Optional[Tuple[float, Dict[str, Scalar]]]):
        """
        Hook called after evaluate (centralized evaluation) to save results.
        
        This method is called automatically through the hook system.
        """
        try:
            if result is not None:
                loss, metrics = result
                
                centralized_eval_data = {
                    "session_id": self.session_id,
                    "round": server_round,
                    "type": "centralized_evaluation",
                    "loss": loss,
                    "metrics": metrics,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
                centralized_file = self._get_file_path(server_round, "centralized_eval")
                self._write_file_safely(centralized_file, centralized_eval_data, is_binary=False)
                
                logm.console.log(f"[FileWritingDecorator] Saved centralized evaluation for round {server_round}")
                
        except Exception as e:
            logm.console.log(f"[FileWritingDecorator] Error in _save_centralized_eval_results: {e}")

    # ============================================
    # UTILITY METHODS (optional)
    # ============================================

    def cleanup_old_files(self, keep_rounds: int = 10):
        """
        Clean up old round files.
        
        Parameters
        ----------
        keep_rounds : int
            Number of recent rounds to keep
        """
        try:
            import glob
            
            pattern = f"session_{self.session_id}_round_*"
            files = glob.glob(str(self.shared_directory / pattern))
            
            # Group by round
            rounds = {}
            for file_path in files:
                filename = Path(file_path).name
                parts = filename.split('_')
                if len(parts) >= 4:
                    try:
                        round_num = int(parts[3])
                        if round_num not in rounds:
                            rounds[round_num] = []
                        rounds[round_num].append(file_path)
                    except ValueError:
                        continue
            
            # suppress old rounds
            sorted_rounds = sorted(rounds.keys(), reverse=True)
            for round_num in sorted_rounds[keep_rounds:]:
                for file_path in rounds[round_num]:
                    try:
                        os.remove(file_path)
                        logm.console.log(f"[FileWritingDecorator] Cleaned up: {file_path}")
                    except Exception as e:
                        logm.console.log(f"[FileWritingDecorator] Error cleaning {file_path}: {e}")
                        
        except Exception as e:
            logm.console.log(f"[FileWritingDecorator] Error during cleanup: {e}")

    def cleanup_all_files(self):
        """
        Clean up ALL round files in the shared directory.
        
        This method removes all files matching the session pattern,
        useful for starting with a clean directory.
        """
        try:
            import glob
            
            pattern = f"session_{self.session_id}_round_*"
            files = glob.glob(str(self.shared_directory / pattern))
            
            logm.console.log(f"[FileWritingDecorator] Found {len(files)} files to cleanup")
            
            for file_path in files:
                try:
                    os.remove(file_path)
                    logm.console.log(f"[FileWritingDecorator] Cleaned up: {file_path}")
                except Exception as e:
                    logm.console.log(f"[FileWritingDecorator] Error cleaning {file_path}: {e}")
            
            logm.console.log(f"[FileWritingDecorator] Cleanup completed: {len(files)} files processed")
                        
        except Exception as e:
            logm.console.log(f"[FileWritingDecorator] Error during cleanup_all_files: {e}")

    def cleanup_all_sessions(self):
        """
        Clean up ALL session files in the shared directory (all sessions).
        
        WARNING: This removes files from ALL sessions, not just the current one.
        """
        try:
            import glob
            
            pattern = "session_*_round_*"
            files = glob.glob(str(self.shared_directory / pattern))
            
            logm.console.log(f"[FileWritingDecorator] Found {len(files)} files from all sessions to cleanup")
            
            for file_path in files:
                try:
                    os.remove(file_path)
                    logm.console.log(f"[FileWritingDecorator] Cleaned up: {file_path}")
                except Exception as e:
                    logm.console.log(f"[FileWritingDecorator] Error cleaning {file_path}: {e}")
            
            logm.console.log(f"[FileWritingDecorator] All sessions cleanup completed: {len(files)} files processed")
                        
        except Exception as e:
            logm.console.log(f"[FileWritingDecorator] Error during cleanup_all_sessions: {e}")

    def set_session_id(self, session_id: str):
        """
        Set the session ID (useful for dynamic configuration).
        
        Parameters
        ----------
        session_id : str
            New session ID
        """
        self.session_id = session_id
        logm.console.log(f"[FileWritingDecorator] Session ID updated to: {session_id}")


# ============================================
# FACTORY FUNCTION (optional for easier usage)
# ============================================

def create_file_writing_decorator(base_strategy, 
                                shared_directory: str = "/tmp/filewriterdecorator",
                                save_individual_results: bool = True,
                                ) -> FileWritingDecorator:
    """
    Factory function to easily create a FileWritingDecorator.
    
    Parameters
    ----------
    base_strategy : Strategy
        Base strategy to decorate
    shared_directory : str
        Directory to save files
    save_individual_results : bool
        Whether to save individual client results
    file_extension : str
        Extension for parameter files
    
    Returns
    -------
    FileWritingDecorator
        Configured decorator
    """
    config_data = ConfigFileWritingDecoratorData(
        shared_directory=shared_directory,
        save_individual_results=save_individual_results,
    )
    
    config = ConfigFileWritingDecorator(
        name="filewriting",
        config=config_data
    )
    
    return FileWritingDecorator(base_strategy, config)