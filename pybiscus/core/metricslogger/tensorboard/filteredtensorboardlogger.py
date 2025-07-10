import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime
import torch

class FilteredTensorBoardLogger:
    """
    Wrapper for TensorBoard logger that automatically filters out non-numeric metrics.
    Only logs int, float, bool, and torch.Tensor values to TensorBoard.
    """
    
    def __init__(self, logger, verbose: bool = True):
        """
        Initialize the filtered logger wrapper.
        
        Args:
            logger: The original TensorBoard logger (e.g., from Lightning)
            verbose: If True, prints warnings when filtering out metrics
        """
        self.logger = logger
        self.verbose = verbose
        self.filtered_count = 0
        self.filtered_keys = set()
        
    def log_metrics(self, metrics: Dict[str, Any], step: Optional[int] = None) -> None:
        """
        Log metrics to TensorBoard, filtering out non-numeric values.
        
        Args:
            metrics: Dictionary of metrics to log
            step: Optional step number for TensorBoard
        """
        if not metrics:
            return
            
        # Filter metrics to keep only TensorBoard-compatible types
        filtered_metrics = self._filter_metrics(metrics)
        
        # Log filtered metrics
        if filtered_metrics:
            self.logger.log_metrics(filtered_metrics, step)
        
        # Report filtering summary if verbose
        if self.verbose and self.filtered_count > 0:
            self._log_filtering_summary()
    
    def _filter_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Union[int, float, bool]]:
        """
        Filter metrics to keep only numeric types compatible with TensorBoard.
        
        Args:
            metrics: Original metrics dictionary
            
        Returns:
            Filtered metrics dictionary with only numeric values
        """
        filtered = {}
        initial_count = len(metrics)
        
        for key, value in metrics.items():
            if self._is_tensorboard_compatible(value):
                # Convert torch tensors to Python scalars if needed
                if isinstance(value, torch.Tensor):
                    if value.numel() == 1:  # Single element tensor
                        filtered[key] = value.item()
                    else:
                        # Skip multi-element tensors for now
                        self._record_filtered(key, value, "multi-element tensor")
                        continue
                else:
                    filtered[key] = value
            else:
                self._record_filtered(key, value, type(value).__name__)
        
        # Update filtering statistics
        filtered_this_call = initial_count - len(filtered)
        self.filtered_count += filtered_this_call
        
        return filtered
    
    def _is_tensorboard_compatible(self, value: Any) -> bool:
        """
        Check if a value is compatible with TensorBoard logging.
        
        Args:
            value: Value to check
            
        Returns:
            True if the value can be logged to TensorBoard
        """
        # Basic numeric types
        if isinstance(value, (int, float, bool)):
            return True
            
        # PyTorch tensors (single element only)
        if isinstance(value, torch.Tensor) and value.numel() == 1:
            return True
            
        # Numpy scalars
        try:
            import numpy as np
            if isinstance(value, (np.integer, np.floating, np.bool_)):
                return True
        except ImportError:
            pass
            
        return False
    
    def _record_filtered(self, key: str, value: Any, reason: str) -> None:
        """Record information about filtered metrics."""
        self.filtered_keys.add(f"{key} ({reason})")
        
        if self.verbose:
            if isinstance(value, str) and len(str(value)) > 50:
                display_value = f"{str(value)[:47]}..."
            else:
                display_value = value
                
            logging.debug(f"Filtered metric '{key}': {display_value} (type: {reason})")
    
    def _log_filtering_summary(self) -> None:
        """Log a summary of filtered metrics."""
        if self.filtered_keys:
            print(f"TensorBoard Logger: Filtered {self.filtered_count} non-numeric metrics")
            if self.verbose and len(self.filtered_keys) <= 10:
                print(f"Filtered keys: {', '.join(sorted(self.filtered_keys))}")
    
    def get_filtering_stats(self) -> Dict[str, Any]:
        """
        Get statistics about filtering.
        
        Returns:
            Dictionary with filtering statistics
        """
        return {
            "total_filtered": self.filtered_count,
            "filtered_keys": sorted(self.filtered_keys),
            "unique_filtered_keys": len(self.filtered_keys)
        }
    
    def reset_stats(self) -> None:
        """Reset filtering statistics."""
        self.filtered_count = 0
        self.filtered_keys.clear()
    
    # Delegate other methods to the original logger
    def __getattr__(self, name):
        """Delegate unknown methods to the original logger."""
        return getattr(self.logger, name)


# Convenience function to create the wrapper
def create_filtered_tensorboard_logger(original_logger, verbose: bool = True):
    """
    Create a filtered TensorBoard logger wrapper.
    
    Args:
        original_logger: The original TensorBoard logger
        verbose: If True, prints warnings when filtering metrics
        
    Returns:
        FilteredTensorBoardLogger instance
    """
    return FilteredTensorBoardLogger(original_logger, verbose=verbose)


# Example usage
if __name__ == "__main__":
    # Example with PyTorch Lightning
    from lightning.pytorch.loggers import TensorBoardLogger
    
    # Create original logger
    original_logger = TensorBoardLogger("logs", name="my_experiment")
    
    # Wrap with filter
    filtered_logger = create_filtered_tensorboard_logger(original_logger, verbose=True)
    
    # Test metrics with mixed types
    test_metrics = {
        "accuracy": 0.95,
        "loss": 0.1,
        "epoch": 10,
        "model_name": "ResNet50",  # Will be filtered
        "timestamp": datetime.now().isoformat(),  # Will be filtered
        "converged": True,
        "learning_rate": 0.001,
        "batch_size": 32
    }
    
    # Log metrics (non-numeric ones will be automatically filtered)
    filtered_logger.log_metrics(test_metrics, step=1)
    
    # Get filtering statistics
    stats = filtered_logger.get_filtering_stats()
    print(f"Filtering stats: {stats}")
    