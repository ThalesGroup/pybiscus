import lightning.pytorch as pl
import torch
from torch.utils.data import DataLoader, Dataset

class VectorDataset(Dataset):

    def __init__(self, num_samples, int_value):
        super().__init__()

        self.num_samples = num_samples
        self.int_value = int_value

        self.data = torch.full((self.num_samples,), self.int_value, dtype=torch.int32)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        return self.data[idx], self.data[idx]

#               -------------------------------

class VectorLightningDataModule(pl.LightningDataModule):

    def __init__(self, num_samples, int_value, batch_size):
        super().__init__()

        self.num_samples = num_samples
        self.int_value = int_value
        self.batch_size = batch_size

    def setup(self, stage=None):
        # Create datasets for training, validation and test
        self.train_dataset = VectorDataset(self.num_samples // 2, self.int_value)
        self.val_dataset   = VectorDataset(self.num_samples // 2, self.int_value)
        self.test_dataset  = VectorDataset(self.num_samples // 2, self.int_value)

    def train_dataloader(self):
        return DataLoader(self.train_dataset, batch_size=self.batch_size, shuffle=True)

    def val_dataloader(self):
        return DataLoader(self.val_dataset, batch_size=self.batch_size)

    def test_dataloader(self):
        return DataLoader(self.test_dataset, batch_size=self.batch_size)

if __name__ == "__main__":

    # Example use
    data_module = VectorLightningDataModule(num_samples=20, int_value=42, batch_size=4)
    data_module.setup()

    # print an example dataset
    train_loader = data_module.train_dataloader()
    batch = next(iter(train_loader))
    print(batch)

