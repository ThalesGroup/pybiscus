import pytorch_lightning as pl
import torch
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

class DecisionTreeModel(pl.LightningModule):
    def __init__(self, max_depth=None):
        super(DecisionTreeModel, self).__init__()
        self.model = DecisionTreeClassifier(max_depth=max_depth)
        self.criterion = accuracy_score

    def forward(self, x):
        return self.model.predict(x)

    def training_step(self, batch, batch_idx):
        x, y = batch
        y_hat = self(x)
        acc = self.criterion(y, y_hat)
        self.log('train_acc', acc)
        return acc

    def validation_step(self, batch, batch_idx):
        x, y = batch
        y_hat = self(x)
        acc = self.criterion(y, y_hat)
        self.log('val_acc', acc)
        return acc

    def fit(self, train_loader):
        x_train, y_train = train_loader.dataset.tensors
        self.model.fit(x_train.numpy(), y_train.numpy())

    def configure_optimizers(self):
        return None  # Pas d'optimiseur nécessaire pour un arbre de décision

# Charger les données Iris
data = load_iris()
X = torch.tensor(data.data, dtype=torch.float32)
y = torch.tensor(data.target, dtype=torch.long)

# Diviser les données en ensembles d'entraînement et de validation
train_loader = DataLoader(TensorDataset(X, y), batch_size=32, shuffle=True)
val_loader = DataLoader(TensorDataset(X, y), batch_size=32)

# Initialiser le modèle
model = DecisionTreeModel(max_depth=3)

# Initialiser le Trainer
trainer = pl.Trainer(max_epochs=1)

# Entraîner le modèle
model.fit(train_loader)
trainer.validate(model, val_loader)

