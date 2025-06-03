from pathlib import Path
import torch
import logging

from pybiscus.flower_config.config_server import ConfigServerOnnxExport, OnnxAxe
import pybiscus.core.pybiscus_logger as logm

logger = logging.getLogger(__name__)


def _deduce_input_names(data_module, input_sample):
    """Automatic deduction of input names"""
    
    # Method 1: DataModule Attributes
    if hasattr(data_module, 'input_names'):
        logm.console.log(f"[onnx] using data module input_names: {data_module.input_names}")
        return data_module.input_names
    
    if hasattr(data_module, 'feature_names'):
        logm.console.log(f"[onnx] using data module feature_names: {data_module.feature_names}")
        return data_module.feature_names
    
    # Method 2 Analyze a dataloader batch
    try:
        data_module.setup()
        dataloader = data_module.train_dataloader()
        batch = next(iter(dataloader))
        
        if isinstance(batch, dict):

            # filter keys that are potential inputs
            input_keys = []
            for key in batch.keys():
                if key.lower() in ['input', 'x', 'data', 'features', 'image', 'text']:
                    input_keys.append(key)
                elif not key.lower() in ['target', 'y', 'label', 'labels', 'ground_truth']:
                    input_keys.append(key)
            
            if input_keys:

                logm.console.log(f"[onnx] deduced name(s) from batch: {input_keys}")
                return input_keys
                
    except Exception as e:
        logm.console.log(f"[onnx] batch input name processing failure: {e}")
    
    # Method 3 check input sample shape
    if len(input_sample.shape) == 4:  # [B, C, H, W]
        logm.console.log(f"[onnx] deduced 'image' name from shape=4")
        return ["image"]
    elif len(input_sample.shape) == 3:  # [B, S, F] ou [B, C, L]
        logm.console.log(f"[onnx] deduced 'sequence' name from shape=3")
        return ["sequence"]
    elif len(input_sample.shape) == 2:  # [B, F]
        logm.console.log(f"[onnx] deduced 'features' name from shape=2")
        return ["features"]
    else:
        logm.console.log(f"[onnx] deduced 'input' name as default")
        return ["input"]


def _deduce_output_names(model, input_sample):
    """Automatic deduction of output names"""
    
    # Method 1: Module Attributes
    if hasattr(model, 'output_names'):
        logm.console.log(f"[onnx] using model output_names: {model.output_names}")
        return model.output_names
    
    if hasattr(model, 'class_names') and hasattr(model, 'num_classes'):
        logm.console.log(f"[onnx] using model 'predictions'")
        return ["predictions"]
    
    # Method 2 Analyze model output
    try:
        model.eval()
        with torch.no_grad():
            output = model(input_sample)
            
        if isinstance(output, dict):
            logm.console.log(f"[onnx] using model dict output {output.keys()}")
            return list(output.keys())
        elif isinstance(output, (list, tuple)):
            logm.console.log(f"[onnx] using model (list, tuple) output")
            return [f"output_{i}" for i in range(len(output))]
        else:
            # Analyse output shape
            if len(output.shape) == 2:  # [B, num_classes]
                if hasattr(model, 'num_classes'):
                    logm.console.log(f"[onnx] using model 'num_classes'")
                    return ["logits"] if model.num_classes > 1 else ["prediction"]
                else:
                    logm.console.log(f"[onnx] using default 'logits'")
                    return ["logits"]
            elif len(output.shape) == 4:  # [B, C, H, W] - segmentation/detection
                logm.console.log(f"[onnx] using model output shape=4")
                return ["segmentation_map"]
            elif len(output.shape) == 3:  # [B, S, F] - sequence
                logm.console.log(f"[onnx] using model output shape=3")
                return ["sequence_output"]
            else:
                logm.console.log(f"[onnx] using default 'output'")
                return ["output"]
                
    except Exception as e:
        logm.console.log(f"[onnx] batch output name processing failure: {e}")
        return ["output"]


def _get_task_specific_names(model):
    """Automatic deduction according to task type"""
    
    # Classification
    if hasattr(model, 'num_classes') or 'classifier' in str(type(model)).lower():
        logm.console.log(f"[onnx] using classification task")
        return {"input": "image", "output": "probabilities"}
    
    # Segmentation
    if 'segmentation' in str(type(model)).lower() or 'unet' in str(type(model)).lower():
        logm.console.log(f"[onnx] using segmentation task")
        return {"input": "image", "output": "segmentation_mask"}
    
    # Detection
    if 'detection' in str(type(model)).lower() or 'yolo' in str(type(model)).lower():
        logm.console.log(f"[onnx] using detection task")
        return {"input": "image", "output": "detections"}
    
    # NLP
    if hasattr(model, 'tokenizer') or 'bert' in str(type(model)).lower():
        logm.console.log(f"[onnx] using NLP task")
        return {"input": "input_ids", "output": "last_hidden_state"}
    
    # Regression
    if hasattr(model, 'criterion') and 'mse' in str(model.criterion).lower():
        logm.console.log(f"[onnx] using regression task")
        return {"input": "features", "output": "prediction"}
    
    return {"input": "input", "output": "output"}


def _deduce_dynamic_axes(model, data_module, input_sample, input_names, output_names):
    """Automatic deduction of dynamic axes"""
    
    dynamic_axes = {}
    
    # === input dynamic axes ===
    for input_name in input_names:
        input_dynamic = {}
        
        # Batch size is almost always dynamic
        input_dynamic[0] = "batch_size"
        
        # analyse input shape for other dynamic axes
        input_shape = input_sample.shape
        
        # Images: height and width may be dynamic
        if len(input_shape) == 4:  # [B, C, H, W]
            # check if the DataModule supports dynamic shapes
            if hasattr(data_module, 'variable_size') and data_module.variable_size:
                input_dynamic[2] = "height"
                input_dynamic[3] = "width"
            elif hasattr(data_module, 'img_size') and isinstance(data_module.img_size, str):
                if 'var' in data_module.img_size.lower():
                    input_dynamic[2] = "height" 
                    input_dynamic[3] = "width"
        
        # Sequences: length often dynamic
        elif len(input_shape) == 3:  # [B, S, F] ou [B, C, L]
            # NLP or temporal series
            if hasattr(data_module, 'max_length') or hasattr(data_module, 'sequence_length'):
                input_dynamic[1] = "sequence_length"
            # audio/1D signals
            elif hasattr(data_module, 'variable_length') and data_module.variable_length:
                input_dynamic[2] = "signal_length"
        
        # Arrays: features number may be dynamic (rare)
        elif len(input_shape) == 2:  # [B, F]
            if hasattr(data_module, 'variable_features') and data_module.variable_features:
                input_dynamic[1] = "num_features"
        
        dynamic_axes[input_name] = input_dynamic
    
    # === output dynamic axes ===
    try:
        model.eval()
        with torch.no_grad():
            output = model(input_sample)
            
        if isinstance(output, dict):
            outputs = output
        elif isinstance(output, (list, tuple)):
            outputs = {name: out for name, out in zip(output_names, output)}
        else:
            outputs = {output_names[0]: output}
            
        for output_name, output_tensor in outputs.items():
            output_dynamic = {}
            output_shape = output_tensor.shape
            
            # Batch size is always dynamic
            output_dynamic[0] = "batch_size"
            
            # Classification: usually fixed class number
            if len(output_shape) == 2:  # [B, num_classes] ou [B, features]
                # special case (detection with varying object number)
                if 'detection' in output_name.lower() or 'bbox' in output_name.lower():
                    output_dynamic[1] = "num_detections"
            
            # Segmentation: image size
            elif len(output_shape) == 4:  # [B, C, H, W]
                if input_sample.shape[0] == output_shape[0]:  # same batch
                    # if input is dynamic, output too
                    if len(dynamic_axes.get(input_names[0], {})) > 1:
                        output_dynamic[2] = "height"
                        output_dynamic[3] = "width"
            
            # output sequences
            elif len(output_shape) == 3:  # [B, S, F]
                # if input sequence is dynamic, output too
                input_dynamic_keys = dynamic_axes.get(input_names[0], {})
                if 1 in input_dynamic_keys:
                    output_dynamic[1] = input_dynamic_keys[1]  # same name
            
            dynamic_axes[output_name] = output_dynamic
            
    except Exception as e:
        logm.console.log(f"[onnx] output dynamic axes deduction failure: {e}")

        # Fallback: only batch_size
        for output_name in output_names:
            dynamic_axes[output_name] = {0: "batch_size"}
    
    # === MODEL KIND SPECIFIC HEURISTICS ===
    model_type = str(type(model)).lower()
    
    # detection models
    if any(word in model_type for word in ['yolo', 'rcnn', 'ssd', 'detection']):
        for output_name in output_names:
            if 'bbox' in output_name.lower() or 'detection' in output_name.lower():
                dynamic_axes[output_name] = {0: "batch_size", 1: "num_detections"}
    
    # NLP models
    elif any(word in model_type for word in ['bert', 'gpt', 'transformer']):
        for input_name in input_names:
            dynamic_axes[input_name] = {0: "batch_size", 1: "sequence_length"}
        for output_name in output_names:
            if len(output_names) > 1 or 'sequence' in output_name.lower():
                dynamic_axes[output_name] = {0: "batch_size", 1: "sequence_length"}
    
    # filter out empty axes
    dynamic_axes = {name: axes for name, axes in dynamic_axes.items() if axes}
    
    logm.console.log(f"[onnx] deduced dynamic axes: {dynamic_axes}")
    return dynamic_axes


def get_model_input_from_datamodule(data_module):
    """DataModule input shape automatic fetch"""
    
    # datamodule setup if required
    if not hasattr(data_module, '_setup_called') or not data_module._setup_called:
        data_module.setup()
    
    # Method 1: attribut input_size
    if hasattr(data_module, 'input_size'):
        input_size = data_module.input_size
        if isinstance(input_size, (list, tuple)):
            return (1,) + tuple(input_size)
        else:
            return (1, input_size)
    
    # Method 2: attribute dims (used by some datamodules)
    if hasattr(data_module, 'dims'):
        return (1,) + tuple(data_module.dims)
    
    # Method 3: fetch a real sample
    try:
        # first try train_dataloader
        dataloader = data_module.train_dataloader()
        batch = next(iter(dataloader))
        
        # manage various batch shape
        if isinstance(batch, dict):
            # dict Batch (ex: {"input": tensor, "target": tensor})
            if 'input' in batch:
                sample = batch['input'][0:1]
            elif 'x' in batch:
                sample = batch['x'][0:1]
            else:
                # fetch the first tensor 
                sample = next(iter(batch.values()))[0:1]
        elif isinstance(batch, (list, tuple)):
            # tuple/liste (input, target) Batch
            sample = batch[0][0:1]  # first element, first sample
        else:
            # Batch is a tensor
            sample = batch[0:1]
            
        return sample.shape
        
    except Exception as e:
        logm.console.log(f"[onnx] fetch from train_dataloader failure: {e}")
                         
        # fallback: try with val_dataloader
        try:
            dataloader = data_module.val_dataloader()
            batch = next(iter(dataloader))
            
            if isinstance(batch, dict):
                if 'input' in batch:
                    sample = batch['input'][0:1]
                elif 'x' in batch:
                    sample = batch['x'][0:1]
                else:
                    sample = next(iter(batch.values()))[0:1]
            elif isinstance(batch, (list, tuple)):
                sample = batch[0][0:1]
            else:
                sample = batch[0:1]
                
            return sample.shape
            
        except Exception as e2:
            logm.console.log(f"[onnx] fetch from val_dataloader failure: {e}")
            raise ValueError(
                "Input shape automatic determination failure."
                "Make sure that the DataModule has attributes 'input_size' or 'dims', "
                "or that we can access to dataloaders."
            )


def to_onnx_with_datamodule(model, data_module, onnx_path: Path, configServerOnnxExport: ConfigServerOnnxExport):
    """ONNX convertion using DataModule specifications"""
    
    # check that model is in  eval mode
    model.eval()
    
    # get input shape
    try:
        input_shape = get_model_input_from_datamodule(data_module)
        logm.console.log(f"[onnx] detected input shape: {input_shape}")
    except Exception as e:
        logm.console.log(f"[onnx] input shape detection failure: {e}")
        raise
    
    # create input sample
    input_sample = torch.randn(*input_shape)
    
    # if necessary, move on the same device
    if hasattr(model, 'device'):
        input_sample = input_sample.to(model.device)
    
    # input and output names based on configuration
    config_input_names = [
        axe.name for axe in configServerOnnxExport.axes
        if axe.kind == OnnxAxe.AxeKind.input
    ]

    config_output_names = [
        axe.name for axe in configServerOnnxExport.axes
        if axe.kind == OnnxAxe.AxeKind.output
    ]
    
    # input names deduction
    input_names = config_input_names or _deduce_input_names(data_module, input_sample)
    
    # output names deduction  
    output_names = config_output_names or _deduce_output_names(model, input_sample)
    
    # Fallback with task specific names
    if not input_names or input_names == ["input"]:
        task_names = _get_task_specific_names(model)
        input_names = [task_names["input"]]
        
    if not output_names or output_names == ["output"]:
        task_names = _get_task_specific_names(model)  
        output_names = [task_names["output"]]
    
    logm.console.log(f"[onnx] Used input names: {input_names}")
    logm.console.log(f"[onnx] Used output names: {output_names}")

    # dynamic axes - configuration vs auto detection
    config_dynamic_axes = {}
    for axe in configServerOnnxExport.axes:
        if axe.dynamic and axe.kind in {OnnxAxe.AxeKind.input, OnnxAxe.AxeKind.output}:
            if hasattr(axe, 'dynamic_dims') and axe.dynamic_dims:
                config_dynamic_axes[axe.name] = axe.dynamic_dims
            else:
                config_dynamic_axes[axe.name] = {0: "batch_size"}
    
    # config is empty: auto detection
    if not config_dynamic_axes:
        dynamic_axes = _deduce_dynamic_axes(model, data_module, input_sample, input_names, output_names)
        logm.console.log("[onnx] Use auto detected dynamic axes")
    else:
        dynamic_axes = config_dynamic_axes
        logm.console.log("[onnx] Use configuration dynamic axes")

    # pre export quick forward pass
    try:
        with torch.no_grad():
            _ = model(input_sample)
        logm.console.log("[onnx] successfull forward pass test")
    except Exception as e:
        logm.console.log(f"[onnx] forward pass test failure: {e}")
        raise ValueError(f"[onnx] The model can not handle such input shape {input_shape}: {e}")

    # ONNX export
    try:
        logm.console.log(f"[onnx]  💾🧠 export in file: {onnx_path}")

        result = model.to_onnx(
            file_path=onnx_path,
            input_sample=input_sample,
            export_params=True,
            opset_version=configServerOnnxExport.opset,
            input_names=input_names,
            output_names=output_names,
            dynamic_axes=dynamic_axes,
            # extra parameters for robustness
            do_constant_folding=True,  # Optimization
            verbose=False,
        )
        logm.console.log("[onnx] successfull export")
        return result
        
    except Exception as e:
        logm.console.log(f"[onnx] export failure: {e}")
        raise


def validate_onnx_export(onnx_path: str, model, input_sample: torch.Tensor, tolerance: float = 1e-5):
    """optional validation of ONNX export"""
    try:
        import onnx
        import onnxruntime as ort
        
        # load ONNX model
        onnx_model = onnx.load(onnx_path)
        onnx.checker.check_model(onnx_model)
        
        # inference test
        ort_session = ort.InferenceSession(onnx_path)
        
        # PyTorch prediction
        model.eval()
        with torch.no_grad():
            pytorch_output = model(input_sample).cpu().numpy()
        
        # ONNX prediction
        input_name = ort_session.get_inputs()[0].name
        onnx_output = ort_session.run(None, {input_name: input_sample.cpu().numpy()})[0]
        
        # Comparison
        diff = abs(pytorch_output - onnx_output).max()
        if diff <= tolerance:
            logm.console.log(f"[onnx] ONNX validation success (max diff: {diff})")
            return True
        else:
            logm.console.log(f"[onnx] difference between PyTorch and ONNX pass threshold: {diff}")
            return False
            
    except ImportError:
        logm.console.log("[onnx] onnx and/or onnxruntime not installed, ignore validation")
        return False
    except Exception as e:
        logm.console.log(f"[onnx]] validation failure: {e}")
        return False
    