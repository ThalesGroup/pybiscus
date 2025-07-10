
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict

from pybiscus.interfaces.flower.clientfactory import ClientFactory

class ConfigFlowerRelayClientData(BaseModel):

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    shared_directory       : str = "/tmp/filewriterdecorator"
    remote_session_id: str = "0"
    timeout: int = 30
    poll_interval: float = 0.5
    max_cache_age_rounds: int = 3
    fail_on_timeout: bool = True

    model_config = ConfigDict(extra="forbid")


class ConfigFlowerRelayClient(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Relay"

    name:   Literal["relay"]
    config: ConfigFlowerRelayClientData

    model_config = ConfigDict(extra="forbid")


class RelayClientFactory(ClientFactory):

    def __init__(self,config,data,model,num_examples):

        self.config=config
        self.data=data
        self.model=model
        self.num_examples=num_examples

    def get_client(self):

        import json
        import pickle
        import time
        from pathlib import Path
        from typing import Dict, List, Tuple, Optional, Any
        from lightning import LightningDataModule, LightningModule
        import numpy as np
        from datetime import datetime

        import flwr as fl
        # from flwr.client import NumPyClient

        import pybiscus.core.pybiscus_logger as logm
        from pybiscus.flower_config.config_computecontext import ConfigClientComputeContext
        from pybiscus.flower_fabric.client.flowerfabricclient.flowerfabricclient import FlowerFabricClient


        class FileReadingTimeoutError(Exception):
            """Custom exception for file reading timeouts."""
            
            def __init__(self, message: str, round_num: int, file_type: str, timeout: int):
                self.round_num = round_num
                self.file_type = file_type
                self.timeout = timeout
                super().__init__(message)


        class GracefullyFailingFileClient(FlowerFabricClient):
            """
            Flower client that fails gracefully when files are not available.
            
            This client:
            - Tries to read files with timeout
            - Uses cached data as fallback (optional)
            - Raises exceptions to be properly counted as failed by Flower server
            - Allows the server to handle failures appropriately
            """

            def __init__(
                self,
                cid: int,
                model: LightningModule,
                data: LightningDataModule,
                num_examples: Dict[str, int],
                conf_fabric: ConfigClientComputeContext,
                shared_directory: str,
                remote_session_id: str,
                timeout: int,
                poll_interval: float,
                use_cache_fallback: bool,
                max_cache_age_rounds,
                fail_on_timeout: bool
            ):
                """
                Initialize the gracefully failing client.
                
                Parameters
                ----------
                cid : int
                    Client identifier
                shared_directory : str
                    Directory where session files are stored
                remote_session_id : str
                    ID of the remote session to read from
                num_examples : Dict[str, int]
                    Number of examples for compatibility with Flower
                timeout : int
                    Timeout in seconds when waiting for files
                poll_interval : float
                    Polling interval in seconds
                use_cache_fallback : bool
                    Whether to use cached data before failing
                max_cache_age_rounds : int
                    Maximum age of cached data in rounds
                fail_on_timeout : bool
                    Whether to raise exception on timeout (True = proper Flower failure)
                """

                # force pre_train_val to False
                pre_train_val = False

                print(f"Paramètres reçus:")
                print(f"  cid: {cid} (type: {type(cid)})")
                print(f"  model: {model} (type: {type(model)})")
                print(f"  data: {data} (type: {type(data)})")
                print(f"  num_examples: {num_examples} (type: {type(num_examples)})")
                print(f"  conf_fabric: {conf_fabric} (type: {type(conf_fabric)})")
                print(f"  shared_directory: {shared_directory} (type: {type(shared_directory)})")
                print(f"  remote_session_id: {remote_session_id} (type: {type(remote_session_id)})")
                print(f"  timeout: {timeout} (type: {type(timeout)})")
                print(f"  poll_interval: {poll_interval} (type: {type(poll_interval)})")
                print(f"  use_cache_fallback: {use_cache_fallback} (type: {type(use_cache_fallback)})")
                print(f"  max_cache_age_rounds: {max_cache_age_rounds} (type: {type(max_cache_age_rounds)})")
                print(f"  fail_on_timeout: {fail_on_timeout} (type: {type(fail_on_timeout)})")
                print(f"  pre_train_val: {pre_train_val} (type: {type(pre_train_val)})")

                super().__init__(cid, model, data, num_examples, conf_fabric, pre_train_val)

                # self.cid = cid
                self.shared_directory = Path(shared_directory)
                self.remote_session_id = remote_session_id
                # self.num_examples = num_examples
                self.timeout = timeout
                self.poll_interval = poll_interval
                self.use_cache_fallback = use_cache_fallback
                self.max_cache_age_rounds = max_cache_age_rounds
                self.fail_on_timeout = fail_on_timeout
                
                # Cache with metadata
                self._cached_parameters = None
                self._cached_parameters_round = -1
                self._cached_fit_metrics = None
                self._cached_fit_metrics_round = -1
                self._cached_eval_metrics = None
                self._cached_eval_metrics_round = -1
                
                # Statistics
                self._timeout_count = 0
                self._cache_hit_count = 0
                self._successful_reads = 0

                logm.console.log(f"[GracefulFailClient {self.cid}] Initialized - fail_on_timeout: {fail_on_timeout}")

            def _get_file_path(self, round_num: int, file_type: str) -> Path:
                """Generate file path for aggregated files."""
                session_id = self.remote_session_id
                
                if file_type == "global_params":
                    filename = f"session_{session_id}_round_{round_num:04d}_global_params.pkl"
                elif file_type == "aggregated_metrics":
                    filename = f"session_{session_id}_round_{round_num:04d}_aggregated_metrics.json"
                elif file_type == "fit_metrics":
                    filename = f"session_{session_id}_round_{round_num:04d}_fit_metrics.json"
                elif file_type == "eval_metrics":
                    filename = f"session_{session_id}_round_{round_num:04d}_eval_metrics.json"
                else:
                    raise ValueError(f"Unknown file type: {file_type}")
                    
                return self.shared_directory / filename

            def _read_file_with_timeout(self, file_path: Path, timeout: int = None) -> Optional[Any]:
                """
                Read file with timeout.
                
                Returns
                -------
                Optional[Any]
                    File content or None if timeout/error
                """

                print(f"_read_file_with_timeout({file_path}, {timeout})")

                if timeout is None:
                    timeout = self.timeout
                    
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    if file_path.exists():
                        try:
                            if file_path.suffix == '.json':
                                with open(file_path, 'r') as f:
                                    data = json.load(f)
                            else:
                                with open(file_path, 'rb') as f:
                                    data = pickle.load(f)
                            
                            logm.console.log(f"[GracefulFailClient {self.cid}] Successfully read: {file_path.name}")
                            self._successful_reads += 1
                            return data
                            
                        except (json.JSONDecodeError, pickle.UnpicklingError, EOFError):
                            # File being written, wait
                            time.sleep(self.poll_interval)
                            continue
                        except Exception as e:
                            logm.console.log(f"[GracefulFailClient {self.cid}] Error reading {file_path}: {e}")
                            return None
                    else:
                        time.sleep(self.poll_interval)
                
                # Timeout occurred
                self._timeout_count += 1
                logm.console.log(f"[GracefulFailClient {self.cid}] Timeout reading {file_path.name} after {timeout}s")
                return None

            def _is_cache_valid(self, cached_round: int, current_round: int) -> bool:
                """
                Check if cached data is still valid.
                
                Parameters
                ----------
                cached_round : int
                    Round when data was cached
                current_round : int
                    Current round
                
                Returns
                -------
                bool
                    True if cache is still valid
                """
                if cached_round < 0:
                    return False
                
                age = current_round - cached_round
                return age <= self.max_cache_age_rounds

            def _try_with_cache_fallback(self, round_num: int, file_type: str, read_func) -> Any:
                """
                Try to read file, with optional cache fallback, then fail if configured.
                
                Parameters
                ----------
                round_num : int
                    Current round number
                file_type : str
                    Type of file being read
                read_func : callable
                    Function to read the file
                
                Returns
                -------
                Any
                    File content
                
                Raises
                ------
                FileReadingTimeoutError
                    If file cannot be read and fail_on_timeout is True
                """
                # Try to read the file
                result = read_func()
                
                if result is not None:
                    # Success - update cache
                    if file_type == "global_params":
                        self._cached_parameters = result
                        self._cached_parameters_round = round_num
                    elif file_type == "fit_metrics":
                        self._cached_fit_metrics = result
                        self._cached_fit_metrics_round = round_num
                    elif file_type in ["eval_metrics", "aggregated_metrics"]:
                        self._cached_eval_metrics = result
                        self._cached_eval_metrics_round = round_num
                    
                    return result
                
                # Failed to read - try cache fallback if enabled
                if self.use_cache_fallback:
                    cached_data = None
                    cached_round = -1
                    
                    if file_type == "global_params":
                        cached_data = self._cached_parameters
                        cached_round = self._cached_parameters_round
                    elif file_type == "fit_metrics":
                        cached_data = self._cached_fit_metrics
                        cached_round = self._cached_fit_metrics_round
                    elif file_type in ["eval_metrics", "aggregated_metrics"]:
                        cached_data = self._cached_eval_metrics
                        cached_round = self._cached_eval_metrics_round
                    
                    if cached_data is not None and self._is_cache_valid(cached_round, round_num):
                        self._cache_hit_count += 1
                        logm.console.log(f"[GracefulFailClient {self.cid}] Using cached {file_type} from round {cached_round}")
                        return cached_data
                
                # No cache available or cache expired - fail if configured
                if self.fail_on_timeout:
                    error_msg = f"Timeout reading {file_type} for round {round_num} from session {self.remote_session_id}"
                    logm.console.log(f"[GracefulFailClient {self.cid}] FAILING: {error_msg}")
                    raise FileReadingTimeoutError(error_msg, round_num, file_type, self.timeout)
                
                # Return None if not configured to fail
                return None

            def get_stats(self) -> Dict[str, Any]:
                """Get client statistics."""
                total_attempts = self._successful_reads + self._timeout_count
                success_rate = self._successful_reads / total_attempts if total_attempts > 0 else 0.0
                
                stats = {
                    "successful_reads": self._successful_reads,
                    "timeout_count": self._timeout_count,
                    "cache_hit_count": self._cache_hit_count,
                    "total_attempts": total_attempts,
                    "success_rate": success_rate,
                    "fail_on_timeout": self.fail_on_timeout,
                    "use_cache_fallback": self.use_cache_fallback
                }

                print(f"[DEBUG] get_stats => {stats}")

                return stats

            def do_clean_metrics(self, metrics, relay_type):
                    
                clean_metrics = {}
                for key, value in metrics.items():
                    if isinstance(value, (int, float, str, bool)):
                        clean_metrics[key] = value
                    else:
                        clean_metrics[key] = str(value)  # Convertir tout le reste
                
                # Ajouter relay info (types sûrs)
                clean_metrics["cid"] = int(self.cid)
                clean_metrics["relay_cid"] = int(self.cid)
                clean_metrics["relay_type"] = relay_type

                return clean_metrics

            # ============================================
            # FLOWER CLIENT INTERFACE METHODS
            # ============================================

            def get_parameters(self, config: Dict[str, Any]) -> List[np.ndarray]:
                """
                Get parameters - may raise exception on timeout.
                """
                round_num = config.get("server_round", 0)
                logm.console.log(f"[GracefulFailClient {self.cid}] get_parameters, round: {round_num}")
                
                def read_params():
                    file_path = self._get_file_path(round_num, "global_params")
                    params = self._read_file_with_timeout(file_path)
                    print(f"[DEBUG] get_parameters.read_params => {params}")
                    return params 
                
                try:
                    # parameters = self._try_with_cache_fallback(round_num, "global_params", read_params)
                    
                    # if parameters is not None:
                    #     return parameters

                    raw_parameters = self._try_with_cache_fallback(round_num, "global_params", read_params)

                    if raw_parameters is not None:
                        # PROTECTION contre les string arrays
                        clean_params = []
                        for param in raw_parameters:
                            if isinstance(param, np.ndarray) and param.dtype.kind in ['f', 'i', 'c']:
                                clean_params.append(param)
                            else:
                                print(f"[Client] SKIPPING invalid parameter: {type(param)} {getattr(param, 'dtype', 'no-dtype')}")
                        
                        # Utilisez clean_params au lieu de raw_parameters
                        return clean_params
                    else:
                        # Return empty list if not configured to fail
                        logm.console.log(f"[GracefulFailClient {self.cid}] Returning empty parameters")
                        return []
                        
                except FileReadingTimeoutError:
                    # Re-raise to be caught by Flower as client failure
                    raise


            def set_parameters(self, parameters: List[np.ndarray]) -> None:
                """Set parameters."""
                logm.console.log(f"[GracefulFailClient {self.cid}] set_parameters")
                # Update cache if we have valid parameters
                if len(parameters) > 0:
                    self._cached_parameters = parameters


            def fit(self, parameters: List[np.ndarray], config: Dict[str, Any]) -> Tuple[List[np.ndarray], int, Dict[str, Any]]:
                """
                Fit - may raise exception on timeout.
                """
                round_num = config.get("server_round", 0)
                logm.console.log(f"[GracefulFailClient {self.cid}] ***fit***, round: {round_num}")
                
                self.set_parameters(parameters)
                
                def read_params():
                    file_path = self._get_file_path(round_num, "global_params")

                    #TODO:
                    params = self._read_file_with_timeout(file_path)
                    print(f"[DEBUG] fit.read_params => {params}")
                    
                    return params
                
                def read_metrics():
                    file_path = self._get_file_path(round_num, "fit_metrics")

                    #TODO:
                    metrics = self._read_file_with_timeout(file_path)
                    print(f"[DEBUG] fit.read_metrics => {metrics}")
                    
                    return metrics
                
                try:
                    # Try to read both parameters and metrics
                    aggregated_params = self._try_with_cache_fallback(round_num, "global_params", read_params)
                    fit_metrics = self._try_with_cache_fallback(round_num, "fit_metrics", read_metrics)
                    
                    if aggregated_params is not None and fit_metrics is not None:

                        # DEBUG: Vérifier les types
                        print(f"[DEBUG] aggregated_params type: {type(aggregated_params)}")
                        print(f"[DEBUG] aggregated_params length: {len(aggregated_params)}")
                        if len(aggregated_params) > 0:
                            print(f"[DEBUG] First param type: {type(aggregated_params[0])}")
                        
                        # FORCER les bons types
                        # 1. Paramètres = liste de numpy arrays
                        clean_params = []

                        for param in aggregated_params:
                            if isinstance(param, np.ndarray):
                                # Vérifier que c'est numérique, sinon ignorer
                                if param.dtype.kind in ['f', 'i', 'c']:  # float, int, complex
                                    clean_params.append(param.astype(np.float32))
                                else:
                                    print(f"[DEBUG] SKIPPING non-numeric array: {param.dtype}")
                            else:
                                try:
                                    clean_params.append(np.array(param, dtype=np.float32))
                                except:
                                    print(f"[DEBUG] SKIPPING unconvertible param: {type(param)}")

                        # 2. Total examples = int Python
                        total_examples = int(fit_metrics.get("total_examples", 1000))
                        
                        # 3. Métriques = dict avec scalaires uniquement
                        clean_metrics = self.do_clean_metrics(fit_metrics, "fit")
                        
                        print(f"[DEBUG] Returning: {len(clean_params)} params, {total_examples}, {len(clean_metrics)} metrics")
                        
                        print(f"TYPE CHECK - params: {type(aggregated_params)}")
                        print(f"TYPE CHECK - examples: {type(total_examples)} = {total_examples}")
                        print(f"TYPE CHECK - metrics keys: {list(fit_metrics.keys())}")
                        print(f"TYPE CHECK - metrics types: {[(k, type(v).__name__) for k, v in fit_metrics.items()]}")

                        return clean_params, total_examples, clean_metrics                        
    
                        ##############################################################################

                        total_examples = fit_metrics.get("total_examples", self.num_examples["trainset"])
                        
                        # Enhance metrics with client stats
                        enhanced_metrics = dict(fit_metrics)
                        enhanced_metrics.update({
                            "cid": self.cid,
                            "relay_cid": self.cid,
                            "relay_stats": self.get_stats(),
                            "relay_timestamp": datetime.now().isoformat()
                        })
                        
                        return aggregated_params, total_examples, enhanced_metrics
                    
                    elif aggregated_params is not None:
                        # Got parameters but no metrics
                        logm.console.log(f"[GracefulFailClient {self.cid}] Got parameters but no metrics")
                        return aggregated_params, self.num_examples["trainset"], {
                            "cid": self.cid,
                            "relay_cid": self.cid,
                            "warning": "missing_fit_metrics",
                            "relay_stats": self.get_stats()
                        }
                    
                    else:
                        # No data available and not configured to fail
                        return parameters, self.num_examples["trainset"], {
                            "cid": self.cid,
                            "relay_cid": self.cid,
                            "warning": "no_data_available",
                            "relay_stats": self.get_stats()
                        }
                        
                except FileReadingTimeoutError as e:
                    # Log the failure and re-raise for Flower to handle
                    logm.console.log(f"[GracefulFailClient {self.cid}] FIT FAILED: {e}")
                    raise  # This will make Flower count this client as failed

            def evaluate(self, parameters: List[np.ndarray], config: Dict[str, Any]) -> Tuple[float, int, Dict[str, Any]]:
                """
                Evaluate - may raise exception on timeout.
                """
                round_num = config.get("server_round", 0)
                logm.console.log(f"[GracefulFailClient {self.cid}] ***evaluate***, round: {round_num}")
                
                self.set_parameters(parameters)
                
                def read_metrics():
                    # Try aggregated_metrics first, then eval_metrics
                    file_path = self._get_file_path(round_num, "aggregated_metrics")
                    result = self._read_file_with_timeout(file_path)
                    print(f"[DEBUG] evaluate.read_metrics 1 => {result}")
                    if result is None:
                        file_path = self._get_file_path(round_num, "eval_metrics")
                        result = self._read_file_with_timeout(file_path)
                        print(f"[DEBUG] evaluate.read_metrics 2 => {result}")
                    return result

                try:
                    eval_metrics = self._try_with_cache_fallback(round_num, "eval_metrics", read_metrics)
                    
                    if eval_metrics is not None:
                        loss = eval_metrics.get("loss_weighted", 
                            eval_metrics.get("loss", 
                            eval_metrics.get("loss_mean", 1.0)))
                        
                        total_examples = eval_metrics.get("total_examples", self.num_examples["valset"])
                        
                        # Enhance metrics with client stats
                        enhanced_metrics = dict(eval_metrics)
                        enhanced_metrics.update({
                            "cid": self.cid,
                            "relay_cid": self.cid,
                            "relay_stats": self.get_stats(),
                            "relay_timestamp": datetime.now().isoformat()
                        })

                        cleaned_enhanced_metrics = self.do_clean_metrics(enhanced_metrics, "evaluate")
                        
                        return loss, total_examples, cleaned_enhanced_metrics
                    
                    else:
                        # No data available and not configured to fail
                        return 1.0, self.num_examples["valset"], {
                            "cid": self.cid,
                            "relay_cid": self.cid,
                            "warning": "no_eval_data_available",
                            "relay_stats": self.get_stats()
                        }
                        
                except FileReadingTimeoutError as e:
                    # Log the failure and re-raise for Flower to handle
                    logm.console.log(f"[GracefulFailClient {self.cid}] EVALUATE FAILED: {e}")
                    raise  # This will make Flower count this client as failed


        # ============================================
        # FACTORY FUNCTIONS FOR DIFFERENT BEHAVIORS
        # ============================================

        def create_strict_failing_client(
                cid: int, 
                shared_directory: str, 
                remote_session_id: str,
                num_examples: Dict[str, int], 
                **kwargs) -> GracefullyFailingFileClient:
            """
            Create a client that always fails on timeout (strict mode).
            
            This client will be properly counted as failed by the Flower server.
            """
            return GracefullyFailingFileClient(
                cid=cid,
                shared_directory=shared_directory,
                remote_session_id=remote_session_id,
                num_examples=num_examples,

                fail_on_timeout=True,
                use_cache_fallback=False,

                **kwargs
            )

        # def create_cache_then_fail_client(cid: int, shared_directory: str, remote_session_id: str,
        #                                  num_examples: Dict[str, int], **kwargs) -> GracefullyFailingFileClient:
        #     """
        #     Create a client that tries cache first, then fails if cache is invalid.
            
        #     This provides a balance between reliability and proper failure handling.
        #     """
        #     return GracefullyFailingFileClient(
        #         cid=cid,
        #         shared_directory=shared_directory,
        #         remote_session_id=remote_session_id,
        #         num_examples=num_examples,
        #         fail_on_timeout=True,
        #         use_cache_fallback=True,
        #         max_cache_age_rounds=2,
        #         **kwargs
        #     )

        # def create_tolerant_client(
        #         cid: int, 
        #         shared_directory: str, 
        #         remote_session_id: str,
        #         num_examples: Dict[str, int], **kwargs) -> GracefullyFailingFileClient:
        #     """
        #     Create a client that never fails (always returns something).
            
        #     This client will never be counted as failed by Flower.
        #     """
        #     return GracefullyFailingFileClient(
        #         cid=cid,
        #         shared_directory=shared_directory,
        #         remote_session_id=remote_session_id,
        #         num_examples=num_examples,
        #         fail_on_timeout=False,
        #         use_cache_fallback=True,
        #         max_cache_age_rounds=5,
        #         **kwargs
        #     )


        # ============================================
        # SERVER SIDE: HANDLING CLIENT FAILURES
        # ============================================

        # class FailureAwareStrategy(fl.server.strategy.FedAvg):
        #     """
        #     Example strategy that properly handles client failures.
        #     """
            
        #     def aggregate_fit(self, server_round, results, failures):
        #         """Handle fit results and failures."""
        #         logm.console.log(f"[FailureAwareStrategy] Round {server_round}: "
        #                         f"{len(results)} successful, {len(failures)} failed clients")
                
        #         # Log failure details
        #         for i, failure in enumerate(failures):
        #             if isinstance(failure, tuple):
        #                 client_proxy, exception = failure
        #                 logm.console.log(f"[FailureAwareStrategy] Client failure {i}: {exception}")
        #             else:
        #                 logm.console.log(f"[FailureAwareStrategy] Client failure {i}: {failure}")
                
        #         # Proceed with aggregation only if we have enough successful clients
        #         if len(results) < self.min_fit_clients:
        #             logm.console.log(f"[FailureAwareStrategy] Not enough successful clients: {len(results)} < {self.min_fit_clients}")
        #             return None, {}
                
        #         # Call parent aggregation
        #         return super().aggregate_fit(server_round, results, failures)
            
        #     def aggregate_evaluate(self, server_round, results, failures):
        #         """Handle evaluation results and failures."""
        #         logm.console.log(f"[FailureAwareStrategy] Round {server_round} eval: "
        #                         f"{len(results)} successful, {len(failures)} failed clients")
                
        #         # Log failure details
        #         for i, failure in enumerate(failures):
        #             if isinstance(failure, tuple):
        #                 client_proxy, exception = failure
        #                 logm.console.log(f"[FailureAwareStrategy] Eval failure {i}: {exception}")
        #             else:
        #                 logm.console.log(f"[FailureAwareStrategy] Eval failure {i}: {failure}")
                
        #         # Proceed with aggregation only if we have enough successful clients
        #         if len(results) < self.min_evaluate_clients:
        #             logm.console.log(f"[FailureAwareStrategy] Not enough successful eval clients: {len(results)} < {self.min_evaluate_clients}")
        #             return None, {}
                
        #         # Call parent aggregation
        #         return super().aggregate_evaluate(server_round, results, failures)

        alt_client_conf = self.config.flower_client.alternate_client_class.config

        return create_strict_failing_client(
            cid=self.config.client_run.cid,
            model=self.model,
            data=self.data,
            num_examples=self.num_examples,
            conf_fabric=self.config.client_compute_context.hardware,

            shared_directory=alt_client_conf.shared_directory,
            remote_session_id=alt_client_conf.remote_session_id,
            timeout = alt_client_conf.timeout,
            poll_interval = alt_client_conf.poll_interval,
            max_cache_age_rounds = alt_client_conf.max_cache_age_rounds,
        )
