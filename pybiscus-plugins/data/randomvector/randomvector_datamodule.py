import lightning.pytorch as pl
import torch
from torch.utils.data import Dataset

from pybiscus.ml.datasplit import limit, make_loader, partition_subset, reject_former_fields

from randomvector.randomvector_dataconfig import FORMER_FIELDS, RandomVectorTestSet, RandomVectorTrainSet, RandomVectorValSet

class RandomVectorDataset(Dataset):
    def __init__(self, num_samples, feature_dim, seed=42):
        super().__init__()
        self.num_samples = num_samples
        self.feature_dim = feature_dim
        self.seed = seed
        # a generator of its own: torch.manual_seed reset the global one at every data set, fixing
        # behind the rest of the code the model's initialization and the order of the batches
        generator = torch.Generator().manual_seed(self.seed)
        self.data = torch.randn(num_samples, feature_dim, generator=generator)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        return self.data[idx], self.data[idx]  # returns the same vector as label

#               -------------------------------

class RandomVectorLightningDataModule(pl.LightningDataModule):
    def __init__(self, feature_dim=1, seed=42, train=None, val=None, test=None, **former_fields):
        super().__init__()
        # pybiscus local passes the YAML's sections unvalidated: validated here
        reject_former_fields(former_fields, FORMER_FIELDS)
        if former_fields:
            raise TypeError(f"unexpected data fields: {sorted(former_fields)}")
        self.feature_dim = feature_dim
        self.seed = seed
        self.train = RandomVectorTrainSet.model_validate(train or {})
        self.val = RandomVectorValSet.model_validate(val or {})
        self.test = RandomVectorTestSet.model_validate(test or {})

    def train_source(self):
        """all the generated training examples, in which the partition picks its share"""
        return RandomVectorDataset(self.train.num_samples, self.feature_dim, self.seed)

    def setup(self, stage=None):
        # Create datasets for training, validation and test; every client draws the same values
        # (same seed): the partition gives each one its own share of them
        self.train_dataset = limit(partition_subset(self.train_source(), self.train.partition), self.train.max_samples)
        self.val_dataset   = limit(RandomVectorDataset(self.val.num_samples, self.feature_dim, self.seed + 1), self.val.max_samples)
        self.test_dataset  = limit(RandomVectorDataset(self.test.num_samples, self.feature_dim, self.seed + 2), self.test.max_samples)

    def train_dataloader(self):
        return make_loader(self.train_dataset, self.train, order_seed=self.train.seed)

    def val_dataloader(self):
        return make_loader(self.val_dataset, self.val)

    def test_dataloader(self):
        return make_loader(self.test_dataset, self.test)

if __name__ == "__main__":

    # Example use
    data_module = RandomVectorLightningDataModule(feature_dim=1, train={"num_samples": 20, "batch_size": 4})
    data_module.setup()

    # print an example dataset
    train_loader = data_module.train_dataloader()
    batch = next(iter(train_loader))
    print(batch)
