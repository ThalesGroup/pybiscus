import lightning.pytorch as pl
import torch
from torch.utils.data import Dataset

from pybiscus.ml.datasplit import limit, make_loader, reject_former_fields

from vector.vector_dataconfig import FORMER_FIELDS, VectorTestSet, VectorTrainSet, VectorValSet

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

    def __init__(self, int_value=42, train=None, val=None, test=None, **former_fields):
        super().__init__()

        # pybiscus local passes the YAML's sections unvalidated: validated here
        reject_former_fields(former_fields, FORMER_FIELDS)
        if former_fields:
            raise TypeError(f"unexpected data fields: {sorted(former_fields)}")
        self.int_value = int_value
        self.train = VectorTrainSet.model_validate(train or {})
        self.val = VectorValSet.model_validate(val or {})
        self.test = VectorTestSet.model_validate(test or {})

    def setup(self, stage=None):
        # Create datasets for training, validation and test
        self.train_dataset = limit(VectorDataset(self.train.num_samples, self.int_value), self.train.max_samples)
        self.val_dataset   = limit(VectorDataset(self.val.num_samples, self.int_value), self.val.max_samples)
        self.test_dataset  = limit(VectorDataset(self.test.num_samples, self.int_value), self.test.max_samples)

    def train_dataloader(self):
        return make_loader(self.train_dataset, self.train)

    def val_dataloader(self):
        return make_loader(self.val_dataset, self.val)

    def test_dataloader(self):
        return make_loader(self.test_dataset, self.test)

if __name__ == "__main__":

    # Example use
    data_module = VectorLightningDataModule(int_value=42, train={"num_samples": 10, "batch_size": 4})
    data_module.setup()

    # print an example dataset
    train_loader = data_module.train_dataloader()
    batch = next(iter(train_loader))
    print(batch)
