import lightning.pytorch as pl
import torch
from torch.utils.data import DataLoader, Dataset

class RandomVectorDataset(Dataset):
    def __init__(self, num_samples, feature_dim, seed=42):
        super().__init__()
        self.num_samples = num_samples
        self.feature_dim = feature_dim
        self.seed = seed
        torch.manual_seed(self.seed)
        self.data = torch.randn(num_samples, feature_dim)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        return self.data[idx], self.data[idx]  # Retourne le même vecteur comme "label"

#               -------------------------------

class RandomVectorLightningDataModule(pl.LightningDataModule):
    def __init__(self, num_samples, feature_dim, batch_size=32, seed=42):
        super().__init__()
        self.num_samples = num_samples
        self.feature_dim = feature_dim
        self.batch_size = batch_size
        self.seed = seed

    def setup(self, stage=None):
        # Créer des datasets pour l'entraînement, la validation et le test
        self.train_dataset = RandomVectorDataset(self.num_samples, self.feature_dim, self.seed)
        self.val_dataset   = RandomVectorDataset(self.num_samples // 2, self.feature_dim, self.seed + 1)
        self.test_dataset  = RandomVectorDataset(self.num_samples // 2, self.feature_dim, self.seed + 2)

    def train_dataloader(self):
        return DataLoader(self.train_dataset, batch_size=self.batch_size, shuffle=True)

    def val_dataloader(self):
        return DataLoader(self.val_dataset, batch_size=self.batch_size)

    def test_dataloader(self):
        return DataLoader(self.test_dataset, batch_size=self.batch_size)

if __name__ == "__main__":

    # Exemple d'utilisation
    data_module = RandomVectorLightningDataModule(num_samples=20, feature_dim=1, batch_size=4)
    data_module.setup()

    # Afficher un batch d'exemple
    train_loader = data_module.train_dataloader()
    batch = next(iter(train_loader))
    print(batch)

