# PyBiscus Integration Guide

## Model Integration

### Step-by-Step Guide to Writing a Model for PyBiscus

### Step 1: Create the Configuration Model

Start by defining your model's configuration using Pydantic BaseModel with the required PyBiscus metadata:

```python
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict, Field

class ConfigYourModel(BaseModel):
    """Configuration for your custom model.
    
    This will be used to generate the GUI form fields.
    """
    
    # REQUIRED: Marks this class for GUI generation
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    
    # Define your model parameters - you can use either Field() or simple defaults
    
    # Full Field() definition with validation and description
    learning_rate: float = Field(
        default=0.001, 
        description="Learning rate for optimizer",
        ge=0.0001,  # GUI will enforce minimum value
        le=0.1      # GUI will enforce maximum value
    )
    
    # Abbreviated syntax - just type and default value
    hidden_size: int = 128
    dropout_rate: float = 0.2
    batch_size: int = 32
    
    # Mix of both approaches as needed
    epochs: int = Field(default=100, description="Number of training epochs", ge=1, le=1000)
    use_batch_norm: bool = True  # Simple boolean with default
    
    # Prevent extra fields
    model_config = ConfigDict(extra="forbid")
```

### Step 2: Create the Model Variant Class

Define the discriminated union variant that links your config to the model:

```python
class ConfigModel_YourModel(BaseModel):
    """Variant class for GUI dropdown selection."""
    
    # REQUIRED: Display name in GUI dropdown
    PYBISCUS_ALIAS: ClassVar[str] = "Your Model Name"
    
    # REQUIRED: Discriminator field for union types
    name: Literal["your_model"]  # Must be unique across all models
    
    # REQUIRED: Link to your configuration
    config: ConfigYourModel
    
    model_config = ConfigDict(extra="forbid")
```

### Step 3: Define the Model Signature

Create a TypedDict that defines what your training/validation steps return:

```python
from typing import TypedDict
import torch

class YourModelSignature(TypedDict):
    """Defines the expected return type for training/validation steps."""
    loss: torch.Tensor
    accuracy: torch.Tensor
    # Add other metrics you want to track
    f1_score: torch.Tensor  # Optional: additional metrics
```

### Step 4: Implement the Lightning Module

Create your PyTorch Lightning module following PyBiscus conventions:

```python
import lightning.pytorch as pl
import torch
import torch.nn as nn
from typing import override
from torchmetrics import Accuracy, F1Score

class LitYourModel(pl.LightningModule):
    """Your PyTorch Lightning model implementation."""
    
    @override
    def __init__(
        self, 
        learning_rate: float,
        hidden_size: int, 
        dropout_rate: float,
        batch_size: int,
        epochs: int,
        use_batch_norm: bool,
        _logging: bool = False,  # PyBiscus logging control
    ):
        super().__init__()
        
        # REQUIRED: Save hyperparameters for checkpointing
        self.save_hyperparameters()
        
        # Store configuration
        self.learning_rate = learning_rate
        self.hidden_size = hidden_size
        self.dropout_rate = dropout_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.use_batch_norm = use_batch_norm
        self._logging = _logging
        
        # Initialize your model architecture
        self.model = self._build_model()
        
        # Define loss and metrics
        self.loss_fn = nn.CrossEntropyLoss()
        self.accuracy = Accuracy(task="multiclass", num_classes=10)
        self.f1_score = F1Score(task="multiclass", num_classes=10)
        
        # REQUIRED: Set signature for type checking
        self._signature = YourModelSignature
    
    def _build_model(self) -> nn.Module:
        """Build your model architecture."""
        layers = []
        layers.append(nn.Linear(784, self.hidden_size))
        if self.use_batch_norm:
            layers.append(nn.BatchNorm1d(self.hidden_size))
        layers.extend([
            nn.ReLU(),
            nn.Dropout(self.dropout_rate),
            nn.Linear(self.hidden_size, self.hidden_size)
        ])
        if self.use_batch_norm:
            layers.append(nn.BatchNorm1d(self.hidden_size))
        layers.extend([
            nn.ReLU(),
            nn.Dropout(self.dropout_rate),
            nn.Linear(self.hidden_size, 10)
        ])
        
        return nn.Sequential(*layers)
    
    @property
    def signature(self):
        """REQUIRED: Expose signature for PyBiscus."""
        return self._signature
    
    @override
    def forward(self, x):
        return self.model(x)
    
    @override
    def training_step(self, batch, batch_idx) -> YourModelSignature:
        """Training step - must return signature-compliant dict."""
        inputs, targets = batch
        
        outputs = self.forward(inputs)
        loss = self.loss_fn(outputs, targets)
        
        # Calculate metrics
        preds = torch.argmax(outputs, dim=1)
        acc = self.accuracy(preds, targets)
        f1 = self.f1_score(preds, targets)
        
        # Optional: Log metrics if enabled
        if self._logging:
            self.log("train_loss", loss, prog_bar=True)
            self.log("train_acc", acc, prog_bar=True)
        
        return {
            "loss": loss,
            "accuracy": acc,
            "f1_score": f1
        }
    
    @override
    def validation_step(self, batch, batch_idx) -> YourModelSignature:
        """Validation step - must return signature-compliant dict."""
        inputs, targets = batch
        
        outputs = self.forward(inputs)
        loss = self.loss_fn(outputs, targets)
        
        preds = torch.argmax(outputs, dim=1)
        acc = self.accuracy(preds, targets)
        f1 = self.f1_score(preds, targets)
        
        if self._logging:
            self.log("val_loss", loss, prog_bar=True)
            self.log("val_acc", acc, prog_bar=True)
            self.log("val_f1", f1, prog_bar=True)
        
        return {
            "loss": loss,
            "accuracy": acc,
            "f1_score": f1
        }
    
    @override
    def test_step(self, batch, batch_idx) -> torch.Tensor:
        """Test step - typically returns loss only."""
        inputs, targets = batch
        outputs = self.forward(inputs)
        return self.loss_fn(outputs, targets)
    
    @override
    def configure_optimizers(self):
        """Configure optimizer and optionally scheduler."""
        optimizer = torch.optim.Adam(
            self.parameters(), 
            lr=self.learning_rate
        )
        
        # Optional: Add scheduler
        scheduler = torch.optim.lr_scheduler.StepLR(
            optimizer, 
            step_size=10, 
            gamma=0.1
        )
        
        return {
            "optimizer": optimizer,
            "lr_scheduler": scheduler
        }
```

## Understanding PyBiscus Metadata

### PYBISCUS_CONFIG: GUI Form Generation Marker

The `PYBISCUS_CONFIG: ClassVar[str] = "config"` metadata serves as a **detection marker** for the PyBiscus GUI generator:

**Purpose:**
- **Class identification**: Tells PyBiscus this class contains configurable parameters
- **Form generation trigger**: Automatically generates HTML form fields from Pydantic `Field()` definitions
- **Metadata processing**: Links the class to the GUI generation pipeline

**How it works:**
1. PyBiscus scans all classes for `PYBISCUS_CONFIG` metadata
2. When found, it introspects the class fields and their `Field()` definitions
3. Generates corresponding HTML form elements (input fields, sliders, dropdowns)
4. Field descriptions become form labels, constraints become validation rules

### PYBISCUS_ALIAS: User-Friendly Display Names

The `PYBISCUS_ALIAS: ClassVar[str] = "Your Model Name"` metadata defines **human-readable names** for the GUI:

**Purpose:**
- **Dropdown labels**: Appears as the option text in model selection dropdowns
- **User experience**: Replaces technical class names with friendly names
- **Documentation**: Provides clear identification for non-technical users

**Example transformation:**
```python
# Technical class name (internal)
class ConfigModel_ComplexNeuralNetwork(BaseModel):
    PYBISCUS_ALIAS: ClassVar[str] = "Deep Neural Network"
    # ...

# GUI displays: "Deep Neural Network" instead of "ConfigModel_ComplexNeuralNetwork"
```

### Discriminated Union Integration

These metadata work together in PyBiscus's discriminated union system:

```python
# High-level model selection structure
class ModelConfiguration(BaseModel):
    model: Union[
        ConfigModel_YourModel,      # name: "your_model"
        ConfigModel_CNN,            # name: "cifar" 
        ConfigModel_ResNet,         # name: "resnet"
        # ... other models
    ] = Field(discriminator="name")
```

**GUI Flow:**
1. **Dropdown population**: `PYBISCUS_ALIAS` values fill the model selection dropdown
2. **Dynamic form generation**: When user selects a model, PyBiscus finds the corresponding config class via `PYBISCUS_CONFIG`
3. **Form rendering**: Generates parameter form from the config class `Field()` definitions
4. **YAML generation**: User input creates structured YAML with the discriminator field

**Generated YAML structure:**
```yaml
model:
  name: your_model           # Discriminator from Literal["your_model"]
  config:                    # From PYBISCUS_CONFIG detection
    learning_rate: 0.001
    hidden_size: 128
    dropout_rate: 0.2
    batch_size: 32
    epochs: 100
    use_batch_norm: true
```

## Configuration Field Syntax

PyBiscus supports two approaches for defining configuration fields, but **field descriptions are extracted from the class docstring**, not from `Field()` descriptions.

### Simple Default Values (Recommended for Most Cases)

```python
class ConfigYourModel(BaseModel):
    """Configuration for your custom model.
    
    Attributes
    ----------
    learning_rate = Learning rate for the optimizer
    hidden_size = Size of hidden layers
    dropout_rate = Dropout probability for regularization
    batch_size = Number of samples per batch
    use_batch_norm = Apply batch normalization layers
    """
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    
    # Simple type and default value - descriptions from docstring
    learning_rate: float = 0.001
    hidden_size: int = 128
    dropout_rate: float = 0.2
    batch_size: int = 32
    use_batch_norm: bool = True
    
    model_config = ConfigDict(extra="forbid")
```

**Benefits:**
- **Concise**: Minimal boilerplate
- **Readable**: Clean and simple syntax
- **Documented**: Descriptions in docstring are easily maintainable
- **Typed**: Maintains type hints for validation

### Field() Definition (Only When Validation Needed)

```python
# Use Field() only for validation constraints
max_epochs: int = Field(default=100, ge=1, le=1000)
learning_rate: float = Field(default=0.001, ge=1e-6, le=0.1)
```

**When to use Field():**
- Need validation constraints (ge, le, gt, lt)
- Complex validation requirements
- Custom validators

**Note**: The `description` parameter in `Field()` is **ignored** by PyBiscus - descriptions must be in the docstring.

## GUI Generation Requirements

### Field Types and Constraints

PyBiscus GUI generator supports these Pydantic field types. **Remember that field descriptions are extracted from the class docstring**, not from `Field()` descriptions:

```python
class ConfigExample(BaseModel):
    """Example configuration showing different field types.
    
    Attributes
    ----------
    int_param = Integer parameter with default
    float_param = Float parameter with default  
    string_param = String parameter with default
    bool_param = Boolean parameter (rendered as checkbox)
    enum_param = Enum parameter (rendered as dropdown)
    validated_param = Integer with validation constraints
    """
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    
    # Simple fields with defaults
    int_param: int = 10
    float_param: float = 0.5
    string_param: str = "default"
    bool_param: bool = True
    
    # Enum fields (rendered as dropdowns)
    from enum import Enum
    class ActivationFunction(str, Enum):
        RELU = "relu"
        TANH = "tanh"
        SIGMOID = "sigmoid"
    
    enum_param: ActivationFunction = ActivationFunction.RELU
    
    # Use Field() only when validation is needed
    validated_param: int = Field(default=10, ge=1, le=100)
```

### Field Descriptions

PyBiscus extracts field descriptions from the **class docstring**, not from `Field()` descriptions. This means you can use simple default values for most fields and document them in the docstring.

**How it works:**
- PyBiscus uses a regex pattern to extract descriptions from the class docstring
- The pattern matches: `attribute_name = description text`
- If no match is found, it falls back to a default format

**Example:**
```python
class ConfigYourModel(BaseModel):
    """Configuration for your custom model.
    
    Attributes
    ----------
    learning_rate = Learning rate for the optimizer
    hidden_size = Number of neurons in hidden layers  
    dropout_rate = Dropout probability for regularization
    batch_size = Number of samples per training batch
    epochs = Maximum number of training epochs
    use_batch_norm = Whether to apply batch normalization
    """
    
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    
    # Simple fields with defaults - descriptions come from docstring
    learning_rate: float = 0.001
    hidden_size: int = 128
    dropout_rate: float = 0.2
    batch_size: int = 32
    epochs: int = 100
    use_batch_norm: bool = True
    
    # Use Field() only when you need validation constraints
    max_epochs: int = Field(default=100, ge=1, le=1000)
    
    model_config = ConfigDict(extra="forbid")
```

**Best practices for docstring descriptions:**
- Use the format: `attribute_name = description text`
- Keep descriptions concise and user-friendly
- Avoid technical jargon when possible
- Document the purpose and expected range/format

### Validation Constraints

- Use `ge=` (greater or equal) and `le=` (less or equal) for numeric ranges
- These constraints will be enforced in the GUI form validation
- Invalid values will be highlighted before YAML generation
- Abbreviated syntax won't have constraints - use `Field()` when validation is needed

## Best Practices

1. **Keep configurations focused**: Only expose parameters that users should modify
2. **Use sensible defaults**: Default values should work for most use cases
3. **Provide clear descriptions**: GUI users may not be ML experts
4. **Validate constraints**: Use Pydantic validators to ensure parameter compatibility
5. **Follow naming conventions**: Use snake_case for consistency
6. **Test your signature**: Ensure training/validation steps return the expected dictionary structure
7. **Choose meaningful aliases**: `PYBISCUS_ALIAS` should be descriptive and user-friendly
8. **Unique discriminators**: Ensure your `name` Literal value is unique across all models
9. **Use docstring for descriptions**: Document fields in the class docstring using the format `field_name = description`
10. **Field() only for validation**: Use `Field()` only when you need constraints - simple defaults are sufficient otherwise
10. **Logical grouping**: Group related parameters together in the class definition

## Model Registration and Integration

### Step 5: Directory Structure and Placement

Your model and configuration files must be placed in the appropriate PyBiscus directory structure. The exact directory locations and naming conventions are defined in the PyBiscus source files `pybiscus/plugin/registries.py` and `registries2.py`, and detailed in the **plugins.md** documentation.

**Option 1: PyBiscus Source Tree (Core Models)**
```
pybiscus/
├── models/
│   ├── your_model/
│   │   ├── __init__.py
│   │   ├── config.py          # ConfigYourModel, ConfigModel_YourModel
│   │   ├── model.py           # LitYourModel implementation
│   │   └── signature.py       # YourModelSignature
│   └── ...
```

**Option 2: External Plugin Directory (Recommended for Custom Models)**
```
my_pybiscus_plugins/
├── your_model/
│   ├── __init__.py
│   ├── config.py
│   ├── model.py
│   └── signature.py
└── ...
```

**Important**: The exact directory structures, naming conventions, and plugin discovery mechanisms are specified in:
- **plugins.md**: User documentation for plugin development
- **pybiscus/plugin/registries.py**: Core registry definitions and discovery logic
- **pybiscus/plugin/registries2.py**: Additional registry configurations

Refer to these files for the authoritative directory structure requirements and plugin registration mechanisms.

### Step 6: Export Function Implementation

You **must** implement the required export function `get_modules_and_configs()` as described in the **how-to.md** documentation, chapter **"How to add models in Pybiscus"**.

Create this function in your model's `__init__.py` file:

```python
# your_model/__init__.py

from .config import ConfigModel_YourModel
from .model import LitYourModel

def get_modules_and_configs():
    """
    REQUIRED: Export function for PyBiscus model registration.
    
    This function is automatically called by PyBiscus during model discovery
    and registration. It must return the configuration class and Lightning module.
    
    Returns:
        tuple: (config_class, lightning_module_class)
            - config_class: The discriminated union config (ConfigModel_YourModel)
            - lightning_module_class: The Lightning module implementation (LitYourModel)
    """
    return ConfigModel_YourModel, LitYourModel
```

### Registration Process

1. **Place your files** in the appropriate directory (source tree or plugin directory)
2. **Implement get_modules_and_configs()** in your model's `__init__.py`
3. **Restart PyBiscus** - it will automatically discover and register your model
4. **Verify registration** - your model should appear in the GUI dropdown with the `PYBISCUS_ALIAS` name

### Integration Verification

After registration, verify your model works correctly:

1. **GUI Integration**: Your model appears in the dropdown as "Your Model Name"
2. **Form Generation**: Selecting your model shows the configuration form with all fields
3. **YAML Export**: Form submission generates valid YAML with proper structure
4. **Model Loading**: PyBiscus can instantiate your Lightning module from the YAML config

### Troubleshooting Registration

**Common issues:**

- **Missing get_modules_and_configs()**: Model won't be discovered
- **Incorrect return tuple**: PyBiscus can't instantiate the model
- **Missing metadata**: GUI generation fails (`PYBISCUS_CONFIG`, `PYBISCUS_ALIAS`)
- **Import errors**: Check all dependencies are available in PyBiscus environment
- **Duplicate discriminators**: Ensure your `name` Literal is unique

**Debug steps:**

1. Check PyBiscus logs for registration errors
2. Verify your `get_modules_and_configs()` function is accessible
3. Test manual import of your config and model classes
4. Ensure all required metadata is properly defined

For detailed plugin development and registration procedures, consult the **plugins.md** and **how-to.md** documentation files in your PyBiscus installation.

---

## Data Provider Integration

### Step-by-Step Guide to Writing a Data Provider for PyBiscus

### Step 1: Create the Data Configuration Model

Start by defining your data provider's configuration using Pydantic BaseModel with the required PyBiscus metadata:

```python
from typing import ClassVar, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

class ConfigYourData(BaseModel):
    """Configuration for your custom data provider.
    
    This will be used to generate the GUI form fields for data parameters.
    """
    
    # REQUIRED: Marks this class for GUI generation
    PYBISCUS_CONFIG: ClassVar[str] = "config"
    
    # Define your data parameters - you can use either Field() or simple defaults
    
    # Directory paths with validation and descriptions
    dir_train: Optional[str] = Field(
        default="${root_dir}/datasets/train/",
        description="Training data directory path"
    )
    
    dir_val: Optional[str] = Field(
        default="${root_dir}/datasets/val/",
        description="Validation data directory path"
    )
    
    dir_test: Optional[str] = Field(
        default="${root_dir}/datasets/test/",
        description="Test data directory path"
    )
    
    # Abbreviated syntax for simple parameters
    batch_size: int = 32
    num_workers: int = 0
    
    # Advanced parameters with validation
    image_size: int = Field(default=224, ge=32, le=1024, description="Input image size")
    data_augmentation: bool = True
    normalize: bool = Field(default=True, description="Apply normalization transforms")
    
    # Prevent extra fields
    model_config = ConfigDict(extra="forbid")
```

### Step 2: Create the Data Provider Variant Class

Define the discriminated union variant that links your config to the data provider:

```python
class ConfigData_YourData(BaseModel):
    """Variant class for GUI dropdown selection."""
    
    # REQUIRED: Display name in GUI dropdown
    PYBISCUS_ALIAS: ClassVar[str] = "Your Dataset Name"
    
    # REQUIRED: Discriminator field for union types
    name: Literal["your_data"]  # Must be unique across all data providers
    
    # REQUIRED: Link to your configuration
    config: ConfigYourData
    
    model_config = ConfigDict(extra="forbid")
```

### Step 3: Implement the Lightning DataModule

Create your PyTorch Lightning DataModule following PyBiscus conventions:

```python
from typing import override, Optional
import lightning.pytorch as pl
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
import pybiscus.core.pybiscus_logger as logm

class YourLightningDataModule(pl.LightningDataModule):
    """
    A LightningDataModule is an abstract class provided by PyTorch Lightning 
    that simplifies data management in machine learning workflows. 
    It helps structure code by separating data preparation logic from the model training logic, 
    making the code more modular and reusable.

    Role:
        1) Data Encapsulation: Centralizes data loading and preparation logic
        2) Reusability: Facilitates reuse across different projects
        3) Integration: Seamlessly integrates with PyTorch Lightning components

    Key Methods:
        - __init__: Initialize with parameters
        - prepare_data: Download data if necessary (called once per node)
        - setup: Prepare datasets for different stages
        - train_dataloader/val_dataloader/test_dataloader: Return DataLoaders
        - teardown: Clean up resources
    """

    @override
    def __init__(
        self,
        dir_train: Optional[str],
        dir_val: Optional[str], 
        dir_test: Optional[str],
        batch_size: int,
        num_workers: int = 0,
        image_size: int = 224,
        data_augmentation: bool = True,
        normalize: bool = True,
    ):
        super().__init__()

        # Store configuration parameters
        self.data_dir_train = dir_train
        self.data_dir_val = dir_val
        self.data_dir_test = dir_test
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.image_size = image_size
        self.data_augmentation = data_augmentation
        self.normalize = normalize

        # Initialize transforms
        self._setup_transforms()

        # Initialize datasets (will be populated in setup())
        self.data_train = None
        self.data_val = None
        self.data_test = None

    def _setup_transforms(self):
        """Setup data transforms based on configuration."""
        transform_list = []
        
        # Resize to target size
        transform_list.append(transforms.Resize((self.image_size, self.image_size)))
        
        # Data augmentation for training
        if self.data_augmentation:
            self.train_transform = transforms.Compose([
                transforms.Resize((self.image_size, self.image_size)),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.RandomRotation(degrees=10),
                transforms.ColorJitter(brightness=0.2, contrast=0.2),
                transforms.ToTensor(),
                transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)) if self.normalize else transforms.Lambda(lambda x: x)
            ])
        else:
            self.train_transform = transforms.Compose([
                transforms.Resize((self.image_size, self.image_size)),
                transforms.ToTensor(),
                transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)) if self.normalize else transforms.Lambda(lambda x: x)
            ])

        # Standard transform for validation/test
        self.eval_transform = transforms.Compose([
            transforms.Resize((self.image_size, self.image_size)),
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)) if self.normalize else transforms.Lambda(lambda x: x)
        ])

    @override
    def prepare_data(self):
        """Download or prepare data if necessary.
        
        This method is called only once per node and is useful for:
        - Downloading datasets
        - Preprocessing that should happen once
        """
        # Add any data download/preparation logic here
        logm.console.log(f"Preparing data from directories:")
        logm.console.log(f"  Train: {self.data_dir_train}")
        logm.console.log(f"  Val: {self.data_dir_val}")
        logm.console.log(f"  Test: {self.data_dir_test}")

    @override
    def setup(self, stage: Optional[str] = None):
        """
        Setup datasets according to stage:

                   | Train | Val | Test |
            -----------------------------
            "fit"  |   X   |  X  |  _   |
            -----------------------------
            "test" |   _   |  _  |  X   |
            -----------------------------
            None   |   X   |  X  |  X   |
            -----------------------------
        """
        
        if stage == "fit" or stage is None:
            if self.data_dir_train:
                self.data_train = ImageFolder(
                    root=self.data_dir_train,
                    transform=self.train_transform
                )
                logm.console.log(f"Training dataset size: {len(self.data_train)}")
                logm.console.log(f"Number of classes: {len(self.data_train.classes)}")
                
            if self.data_dir_val:
                self.data_val = ImageFolder(
                    root=self.data_dir_val,
                    transform=self.eval_transform
                )
                logm.console.log(f"Validation dataset size: {len(self.data_val)}")

        if stage == "test" or stage is None:
            if self.data_dir_test:
                self.data_test = ImageFolder(
                    root=self.data_dir_test,
                    transform=self.eval_transform
                )
                logm.console.log(f"Test dataset size: {len(self.data_test)}")

    @override
    def train_dataloader(self) -> DataLoader:
        """Return DataLoader for training dataset."""
        if self.data_train is None:
            raise ValueError("Train dataset undefined: bad setup or missing data directory")
        
        return DataLoader(
            self.data_train,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=True,
            drop_last=True,
            pin_memory=True  # Speeds up GPU transfer
        )

    @override
    def val_dataloader(self) -> DataLoader:
        """Return DataLoader for validation dataset."""
        if self.data_val is None:
            raise ValueError("Validation dataset undefined: bad setup or missing data directory")
        
        return DataLoader(
            self.data_val,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=False,
            drop_last=False,
            pin_memory=True
        )

    @override
    def test_dataloader(self) -> DataLoader:
        """Return DataLoader for test dataset."""
        if self.data_test is None:
            raise ValueError("Test dataset undefined: bad setup or missing data directory")
        
        return DataLoader(
            self.data_test,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=False,
            drop_last=False,
            pin_memory=True
        )

    @override
    def teardown(self, stage: Optional[str] = None):
        """Clean up resources after training/testing."""
        # Add cleanup logic if needed
        pass
```

## Understanding PyTorch Lightning DataModule

### Core Components

**DataLoader**: A crucial PyTorch component for efficiently loading and iterating over datasets:
- **Batching**: Automatically groups data samples into batches
- **Shuffling**: Randomly shuffles data at each epoch
- **Parallel Loading**: Uses multiple subprocesses for faster data loading
- **Customization**: Allows custom behavior through various parameters

**Key DataLoader Parameters**:
- `dataset`: The dataset instance to load from
- `batch_size`: Number of samples per batch
- `shuffle`: Whether to shuffle data at each epoch
- `num_workers`: Number of subprocesses for data loading
- `drop_last`: Whether to drop incomplete final batch
- `pin_memory`: Speeds up GPU transfer when True

**Dataset Interface**: Abstract class providing consistent data access:
- `__len__()`: Returns dataset size
- `__getitem__(index)`: Retrieves sample and label at given index

### Data Provider Registration

### Step 4: Directory Structure and Placement

Your data provider files must be placed in the appropriate PyBiscus directory structure. The exact directory locations and naming conventions are defined in the PyBiscus source files `pybiscus/plugin/registries.py` and `registries2.py`, and detailed in the **plugins.md** documentation.

**Option 1: PyBiscus Source Tree (Core Data Providers)**
```
pybiscus/
├── data/
│   ├── your_data/
│   │   ├── __init__.py
│   │   ├── config.py          # ConfigYourData, ConfigData_YourData
│   │   └── datamodule.py      # YourLightningDataModule implementation
│   └── ...
```

**Option 2: External Plugin Directory (Recommended for Custom Data Providers)**
```
my_pybiscus_plugins/
├── data/
│   ├── your_data/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── datamodule.py
│   └── ...
```

**Important**: The exact directory structures, naming conventions, and plugin discovery mechanisms are specified in:
- **plugins.md**: User documentation for plugin development
- **pybiscus/plugin/registries.py**: Core registry definitions and discovery logic
- **pybiscus/plugin/registries2.py**: Additional registry configurations

Refer to these files for the authoritative directory structure requirements and plugin registration mechanisms.

### Step 5: Export Function Implementation

You **must** implement the required export function `get_modules_and_configs()` for data providers as described in the **how-to.md** documentation.

Create this function in your data provider's `__init__.py` file:

```python
# your_data/__init__.py

from .config import ConfigData_YourData
from .datamodule import YourLightningDataModule

def get_modules_and_configs():
    """
    REQUIRED: Export function for PyBiscus data provider registration.
    
    This function is automatically called by PyBiscus during data provider discovery
    and registration. It must return the configuration class and DataModule.
    
    Returns:
        tuple: (config_class, datamodule_class)
            - config_class: The discriminated union config (ConfigData_YourData)
            - datamodule_class: The DataModule implementation (YourLightningDataModule)
    """
    return ConfigData_YourData, YourLightningDataModule
```

### Data Provider Configuration Patterns

### Directory Path Configuration

Data providers typically use configurable directory paths with PyBiscus variable substitution:

```python
# Use PyBiscus variables for flexible path configuration
dir_train: Optional[str] = "${root_dir}/datasets/train/"
dir_val: Optional[str] = "${root_dir}/datasets/val/"
dir_test: Optional[str] = "${root_dir}/datasets/test/"

# Or with Field() for better documentation
data_root: str = Field(
    default="${root_dir}/datasets/",
    description="Root directory for all dataset files"
)
```

### Transform Configuration

Expose data augmentation and preprocessing options:

```python
# Image processing parameters
image_size: int = Field(default=224, ge=32, le=1024)
normalize: bool = True
data_augmentation: bool = True

# Advanced augmentation parameters
rotation_degrees: float = Field(default=10.0, ge=0.0, le=45.0)
brightness_factor: float = Field(default=0.2, ge=0.0, le=1.0)
horizontal_flip_prob: float = Field(default=0.5, ge=0.0, le=1.0)
```

### Performance Configuration

Include performance-related parameters:

```python
batch_size: int = Field(default=32, ge=1, le=512)
num_workers: int = Field(default=0, ge=0, le=16, description="Number of data loading workers")
pin_memory: bool = Field(default=True, description="Pin memory for faster GPU transfer")
prefetch_factor: int = Field(default=2, ge=1, le=10)
```

## Data Provider Best Practices

1. **Flexible path configuration**: Use PyBiscus variable substitution for paths
2. **Error handling**: Validate data directories exist and contain expected structure
3. **Comprehensive logging**: Log dataset sizes, classes, and configuration details
4. **Transform customization**: Allow users to configure data augmentation
5. **Performance optimization**: Expose relevant DataLoader performance parameters
6. **Stage-specific setup**: Properly handle "fit", "test", and None stages
7. **Resource management**: Implement proper cleanup in teardown()
8. **Documentation**: Provide clear descriptions for all configuration parameters

### Registration Process

1. **Place your files** in the appropriate directory structure
2. **Implement get_modules_and_configs()** in your data provider's `__init__.py`
3. **Restart PyBiscus** - it will automatically discover and register your data provider
4. **Verify registration** - your data provider should appear in the GUI dropdown

### Integration Verification

After registration, verify your data provider works correctly:

1. **GUI Integration**: Your data provider appears in the dropdown as "Your Dataset Name"
2. **Form Generation**: Selecting your data provider shows the configuration form
3. **YAML Export**: Form submission generates valid YAML configuration
4. **DataModule Loading**: PyBiscus can instantiate your DataModule from the YAML config
5. **Data Loading**: Test that all DataLoaders work correctly in different stages

For detailed plugin development and registration procedures, consult the **plugins.md** and **how-to.md** documentation files in your PyBiscus installation.