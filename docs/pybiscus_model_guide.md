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
    
    # every field with Field(): its description is the form's tooltip, its constraints are
    # checked by `pybiscus check` and the forms
    learning_rate: float = Field(default=0.001, ge=0.0001, le=0.1, description="learning rate of the optimizer")
    hidden_size: int = Field(default=128, ge=1, description="units of the hidden layers")
    dropout_rate: float = Field(default=0.2, ge=0, lt=1, description="probability of dropping a unit while training")
    use_batch_norm: bool = Field(default=True, description="normalize the activations of each batch")

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

**Tooltips:** hovering a field's name (or a section's title) shows its description, taken from
`Field(description=...)`, else from a `name = description` or numpy-style `name:` line of the config
class's docstring. A field without either gets no tooltip. An `Enum` field can describe each of its
values, shown when hovering that value:

```python
class Scheme(str, Enum):
    iid = "iid"
    dirichlet = "dirichlet"

# Enum members cannot carry a docstring, nor a class attribute (it would become a member)
Scheme.PYBISCUS_DESCRIPTIONS = {"iid": "equal shares drawn at random",
                                "dirichlet": "heterogeneous shares"}

class ConfigMyData(BaseModel):
    scheme: Scheme = Field(default=Scheme.iid, description="how the examples are shared")
```

A subclass that redefines a field (another default) keeps its parent's description. A data plugin
whose sections do not derive from `pybiscus.ml.datasplit`'s takes the descriptions of the common
loader fields from `SET_FIELDS` there (`Field(default=32, ge=1, description=SET_FIELDS["batch_size"])`),
so that every plugin says the same thing about the same field.

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

Declare each field with `Field()`: its `description` is shown on hover in the forms, and its
constraints are checked by `pybiscus check` and the forms.

```python
from enum import Enum

class Activation(str, Enum):
    relu = "relu"
    tanh = "tanh"

Activation.PYBISCUS_DESCRIPTIONS = {"relu": "max(0, x)", "tanh": "hyperbolic tangent"}

class ConfigYourModel(BaseModel):
    """your model's parameters"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    learning_rate: float = Field(default=0.001, gt=0, le=0.1, description="learning rate of the optimizer")
    hidden_size: int = Field(default=128, ge=1, description="units of the hidden layers")
    dropout_rate: float = Field(default=0.2, ge=0, lt=1, description="probability of dropping a unit while training")
    use_batch_norm: bool = Field(default=True, description="normalize the activations of each batch")
    activation: Activation = Field(default=Activation.relu, description="activation of the hidden layers")

    model_config = ConfigDict(extra="forbid")
```

How the forms render the types: `int` and `float` as numbers, `str` as text, `bool` as a
checkbox, an `Enum` as one choice per value (with `PYBISCUS_DESCRIPTIONS` on hover), `Optional[X]`
as a section to tick, a `Union` of configurations as tabs, a `list` as items to add and remove.

When a field has no `description`, the form falls back to the class docstring: a line
`field_name = description`, or numpy's `field_name:` with the description on the following lines.
A field described nowhere has no tooltip.

### Validation Constraints

- Use `ge=` (greater or equal) and `le=` (less or equal) for numeric ranges
- These constraints will be enforced in the GUI form validation
- Invalid values will be highlighted before YAML generation

## Best Practices

1. **Keep configurations focused**: Only expose parameters that users should modify
2. **Use sensible defaults**: Default values should work for most use cases
3. **Provide clear descriptions**: GUI users may not be ML experts
4. **Validate constraints**: Use Pydantic validators to ensure parameter compatibility
5. **Follow naming conventions**: Use snake_case for consistency
6. **Test your signature**: Ensure training/validation steps return the expected dictionary structure
7. **Choose meaningful aliases**: `PYBISCUS_ALIAS` should be descriptive and user-friendly
8. **Unique discriminators**: Ensure your `name` Literal value is unique across all models
9. **Describe every field**: `Field(description=...)`, shown on hover in the forms
10. **Constrain the values**: `ge`, `gt`, `le`, `lt` in `Field()`, so that a wrong value is refused at `check`
11. **Logical grouping**: Group related parameters together in the class definition

## Model Registration and Integration

### Step 5: Directory Structure and Placement

Your model and configuration files must be placed in the appropriate PyBiscus directory structure. The exact directory locations and naming conventions are defined in the PyBiscus source files `pybiscus/plugin/registries/model_registry.py`, and detailed in the **plugins.md** documentation.

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
- **pybiscus/plugin/registries/*_registry.py**: Core registry definitions and discovery logic

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

A data plugin describes its data in **sections**: `train` (what a client trains on), `val` (what it
validates on), `test` (the final evaluation, the server's), and optionally `privacy` (the examples
a privacy evaluation attacks). `pybiscus.ml.datasplit` provides the sections, the loaders and the
sharing of the training examples between the clients (`train.partition`), the held-out validation
(`val.source: holdout`), `max_samples`, and their descriptions: a plugin built on them gets all of
these with its datasets only to write. `pybiscus-plugins/data/mnist` is the reference below.

### Step 1: Create the Data Configuration Model

Derive each section from `datasplit`'s to give it your defaults (a field redefined keeps its
description):

```python
from typing import ClassVar, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybiscus.ml.datasplit import (
    ConfigPrivacySet, ConfigTestSet, ConfigTrainSet, ConfigValSet,
    downloaded, limit, make_loader, privacy_loader, privacy_set, reject_former_fields, train_and_val_sets,
)

class YourTrainSet(ConfigTrainSet):
    dir: str = "${root_dir}/datasets/your_data/train/"
    batch_size: int = Field(default=64, ge=1)

class YourValSet(ConfigValSet):
    dir: str = "${root_dir}/datasets/your_data/val/"

class YourTestSet(ConfigTestSet):
    dir: str = "${root_dir}/datasets/your_data/test/"

class ConfigYourData(BaseModel):
    """your dataset, in train / val / test sections"""

    PYBISCUS_CONFIG: ClassVar[str] = "config"

    train: YourTrainSet = Field(default=YourTrainSet(), description="the examples a client trains on")
    val: YourValSet = Field(default=YourValSet(), description="the examples a client validates on")
    test: YourTestSet = Field(default=YourTestSet(), description="the examples of the final evaluation (the server's)")
    privacy: Optional[ConfigPrivacySet] = Field(default=None, description="the examples a privacy evaluation attacks")
    num_workers: int = Field(default=0, ge=0, description="processes loading the batches; 0: the main process")
    image_size: int = Field(default=224, ge=32, le=1024, description="input image size")

    model_config = ConfigDict(extra="forbid")

    # former flat fields (dir_train, batch_size...) refused with where they went
    @model_validator(mode="before")
    @classmethod
    def _former_fields(cls, data):
        return reject_former_fields(data)
```

What each section offers (see [Config files](configuration.md#data) for the YAML side):

| section | fields |
|---|---|
| `train` | `dir`, `batch_size`, `shuffle`, `drop_last`, `seed` (batch order), `indices` (a file of indices) or `partition` (this client's share: `iid`, `dirichlet`, `shards`), `max_samples` |
| `val` | `source`: `official` (the official test split), `holdout` (`fraction` of the client's own share, drawn with `seed`) or `indices`; `dir`, loader options, `max_samples` |
| `test` | `dir`, loader options, `max_samples` |
| `privacy` | `dir`, `batch_size`, `max_samples` (the examples keep their original indices) |

A dataset that does not fit these sections (sequences, engines...) defines its own, and takes
the descriptions of the common fields from `SET_FIELDS` (`hdfs`, `turbofan` and `randomvector` do).

### Step 2: Create the Data Provider Variant Class

```python
class ConfigData_YourData(BaseModel):

    PYBISCUS_ALIAS: ClassVar[str] = "Your Dataset Name"   # label in the forms

    name: Literal["your_data"]    # must equal the registry key, unique across data plugins
    config: ConfigYourData

    model_config = ConfigDict(extra="forbid")
```

### Step 3: Implement the Lightning DataModule

The DataModule receives the sections as dictionaries (`config.model_dump()`), validates them, and
builds its datasets with the helpers:

```python
import lightning.pytorch as pl
import torchvision.transforms as transforms
from torchvision.datasets import MNIST   # your dataset class

class YourLightningDataModule(pl.LightningDataModule):

    def __init__(self, train=None, val=None, test=None, privacy=None, num_workers: int = 0,
                 image_size: int = 224):
        super().__init__()
        self.train = YourTrainSet.model_validate(train or {})
        self.val = YourValSet.model_validate(val or {})
        self.test = YourTestSet.model_validate(test or {})
        self.privacy = None if privacy is None else ConfigPrivacySet.model_validate(privacy)
        self.data_privacy = None
        self.num_workers = num_workers
        self.transform = transforms.Compose([transforms.ToTensor()])

    def train_source(self, dir=None):
        """the whole official train split, in which partitions, holdouts and indices files pick
        their examples (also used by `pybiscus data partition`)"""
        # downloaded(): one download at a time per directory, for clients starting together
        return downloaded(MNIST, dir or self.train.dir, train=True, transform=self.transform)

    def setup(self, stage=None):
        if stage in ("fit", None):
            official_val = lambda: downloaded(MNIST, self.val.dir, train=False, transform=self.transform)
            # partition, holdout or indices applied as the sections say
            self.data_train, self.data_val = train_and_val_sets(self.train_source(), official_val, self.train, self.val)
        if stage in ("test", None):
            self.data_test = limit(downloaded(MNIST, self.test.dir, train=False, transform=self.transform),
                                   self.test.max_samples)
            if self.privacy is not None:
                self.data_privacy = privacy_set(self.train_source(self.privacy.dir), self.privacy)

    def train_dataloader(self):
        return make_loader(self.data_train, self.train, self.num_workers, order_seed=self.train.seed)

    def val_dataloader(self):
        return make_loader(self.data_val, self.val, self.num_workers)

    def test_dataloader(self):
        return make_loader(self.data_test, self.test, self.num_workers)

    def privacy_dataloader(self):
        """None without a privacy section"""
        return None if self.data_privacy is None else privacy_loader(self.data_privacy, self.privacy, self.num_workers)
```

The batches are `(inputs, labels)` pairs: the training loop takes each batch's size from the
inputs' first dimension to average the metrics over the examples.

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

Your data provider files must be placed in the appropriate PyBiscus directory structure. The exact directory locations and naming conventions are defined in the PyBiscus source files `pybiscus/plugin/registries/data_registry.py`, and detailed in the **plugins.md** documentation.

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
- **pybiscus/plugin/registries/*_registry.py**: Core registry definitions and discovery logic

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

Directories go in the sections (`train.dir`, `val.dir`, `test.dir`); `${root_dir}` in a default is
resolved at validation:

```python
class YourTrainSet(ConfigTrainSet):
    dir: str = "${root_dir}/datasets/your_data/train/"
```

A dataset shipped with the plugin can default to the plugin's own directory instead
(`str(Path(__file__).parent / "train.csv")`, as hdfs and turbofan do).

### Transform Configuration

Expose data augmentation and preprocessing options next to the sections:

```python
image_size: int = Field(default=224, ge=32, le=1024, description="input image size")
rotation_degrees: float = Field(default=10.0, ge=0.0, le=45.0, description="random rotation of the training images")
horizontal_flip_prob: float = Field(default=0.5, ge=0.0, le=1.0, description="probability of flipping a training image")
```

### Performance Configuration

`batch_size`, `shuffle` and `drop_last` belong to each section (the loaders differ: shuffled
training, every example evaluated); `num_workers` is shared:

```python
num_workers: int = Field(default=0, ge=0, le=16, description="processes loading the batches; 0: the main process")
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