from typing import override, Optional

import numpy as np
import lightning.pytorch as pl
import torchvision.transforms as transforms

from torch.utils.data import DataLoader
from torchvision.datasets import CIFAR10

import pybiscus.core.pybiscus_logger as logm
from pybiscus.ml.datasplit import downloaded, limit, make_loader, privacy_loader, privacy_set, reject_former_fields, train_and_val_sets

from cifar10.cifar10_dataconfig import CifarPrivacySet, CifarTestSet, CifarTrainSet, CifarValSet

class CifarLightningDataModule(pl.LightningDataModule):
    """CIFAR-10 from torchvision: 32 x 32 colour images of 10 classes, 50,000 to train and 10,000 to test,
    read from the dataset's directories; the shared train, val, test and privacy sections choose the
    examples, the partition between clients and the loaders."""

    @override
    def __init__( self, train=None, val=None, test=None, privacy=None, num_workers: int = 0, **former_fields):

        super().__init__()

        # pybiscus local passes the YAML's sections unvalidated: validated here
        reject_former_fields(former_fields)
        if former_fields:
            raise TypeError(f"unexpected data fields: {sorted(former_fields)}")
        self.train          = CifarTrainSet.model_validate(train or {})
        self.val            = CifarValSet.model_validate(val or {})
        self.test           = CifarTestSet.model_validate(test or {})
        self.privacy        = None if privacy is None else CifarPrivacySet.model_validate(privacy)
        self.num_workers    = num_workers

        self.transform      = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
            ]
        )

        # DataLoaders for train, val and test phasis
        self.data_train     = None
        self.data_val       = None
        self.data_test      = None
        self.data_privacy   = None

    @override
    def setup(self, stage: Optional[str] = None):
        """
        data downloaded according to stage:

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
            train_full = self.train_source()
            logm.console.log("x_train shape: ", train_full.data.shape)

            # print number of targets and  values targets
            logm.console.log("Number of Targets :", len(np.unique(train_full.targets)))
            logm.console.log("Targets Values    :",     np.unique(train_full.targets))

            official_val = lambda: downloaded(CIFAR10, self.val.dir, train=False, transform=self.transform)
            self.data_train, self.data_val = train_and_val_sets(train_full, official_val, self.train, self.val)

        if stage == "test" or stage is None:
            test_full       = downloaded(CIFAR10, self.test.dir, train=False, transform=self.transform)
            logm.console.log("x_test shape", test_full.data.shape)
            self.data_test  = limit( test_full, self.test.max_samples)
            if self.privacy is not None:
                self.data_privacy = privacy_set( self.train_source(self.privacy.dir), self.privacy)

    def train_source(self, dir=None):
        """the official train split, in which the partitions and indices files pick their examples"""
        return downloaded(CIFAR10, dir or self.train.dir, train=True, transform=self.transform)

    @override
    def train_dataloader(self) -> DataLoader:

        if self.data_train is None:
            raise ValueError("Train dataset undefined: bad setup")
        
        return make_loader( self.data_train, self.train, self.num_workers, order_seed=self.train.seed,)

    @override
    def val_dataloader(self) -> DataLoader:

        if self.data_val is None:
            raise ValueError("Val dataset undefined: bad setup")
        
        return make_loader( self.data_val, self.val, self.num_workers,)

    @override
    def test_dataloader(self) -> DataLoader:

        if self.data_test is None:
            raise ValueError("Test dataset undefined: bad setup")
        
        return make_loader( self.data_test, self.test, self.num_workers,)

    def privacy_dataloader(self) -> Optional[DataLoader]:
        """None without a privacy section"""
        if self.data_privacy is None:
            return None
        return privacy_loader( self.data_privacy, self.privacy, self.num_workers,)
