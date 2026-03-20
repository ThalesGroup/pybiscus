from collections import Counter
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
import pandas as pd
import csv
import lightning.pytorch as pl
import numpy as np
import torch
import csv 
from typing import override, Optional

import pybiscus.core.pybiscus_logger as logm

# ------------------------------------------------------------

class HDFSDataset(Dataset):
    def __init__(self, data_path, window_size):
        super().__init__()
        self.num_classes = 33
        self.window_size = window_size
        self.data, self.labels = self.read_data(data_path)



    def read_data(self,data_path):
        with open(data_path, 'r') as read_obj: 

            # Return a reader object which will 
            # iterate over lines in the given csvfile 
            csv_reader = csv.reader(read_obj) 

            # convert string to list 
            list_of_csv = list(csv_reader) 

            list_of_csv = list(map(lambda x: [int(xi) for xi in x], list_of_csv))

            data, label = self.preprocess_data(list_of_csv)       

        return data,label

    def preprocess_data(self,data):
        result_logs = []
        labels = []

        for sequence in data:
            # Convert the sequence to a tuple of integers (subtract 1 to make it 0-indexed)
            sequence = tuple(map(lambda n: n - 1, map(int, sequence)))

            for i in range(len(sequence) - self.window_size):
                sequential_pattern = list(sequence[i:i + self.window_size])
                
                sequential_pattern = np.array(sequential_pattern)[:,np.newaxis]

                result_logs.append(sequential_pattern)
                labels.append(sequence[i + self.window_size])

        return result_logs, labels

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return torch.tensor(self.data[idx], dtype=torch.float), self.labels[idx]
    
# ------------------------------------------------------------

class HDFSTestDataset(Dataset):
    def __init__(self, data_path, window_size):
        super().__init__()
        self.window_size = window_size
        self.sequences, self.counts,self.labels = self.read_data(data_path)
  
    def pad_list_of_lists(self,sequences,pad_value=0):
        max_len = max(len(seq) for seq in sequences)
        return [list(seq) + [pad_value] * (max_len - len(seq)) for seq in sequences]

    def read_data(self,data_path):
        test_data = pd.read_csv(data_path)
        hdfs_dict, labels_dict, length = self.generate(test_data)
        sequences = list(hdfs_dict.keys())
        counts = list(hdfs_dict.values())
        labels = list(labels_dict.values())
        sequences_padded = self.pad_list_of_lists(sequences,pad_value=-99)
        return sequences_padded,counts,labels  

    def generate(self,test_data:pd.DataFrame):
        hdfs_dict = {}
        labels_dict = {}
        length = 0
        for index,row in test_data.iterrows():
            # Convert strings to integers and shift by -1
            row_list = row['seq'].split(',')
            ln = list(map(lambda n: int(n) - 1, row_list))
            # Pad with -1 to the required length
            ln = ln + [-1] * (self.window_size + 1 - len(ln))
            seq_count = hdfs_dict.get(tuple(ln), 0) + 1
            hdfs_dict[tuple(ln)] = seq_count
            labels_dict[tuple(ln)] = row['label']
            length += 1
        return hdfs_dict, labels_dict,length

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return torch.tensor(self.sequences[idx], dtype=torch.float), tuple([self.counts[idx],self.labels[idx]])

# ------------------------------------------------------------

class HDFSDataModule(pl.LightningDataModule):
    def __init__(
        self, 
        train_file: str | None = None, 
        test_file: str | None = None, 
        val_file: str | None = None, 
        batch_size: int = 32, 
        window_size: int = 10,
    ):
        super().__init__()
        self.train_file = train_file
        self.test_file = test_file
        self.val_file = val_file
        self.batch_size = batch_size
        self.window_size = window_size

    def setup(self, stage: str=None):
        """
        Data downloaded according to stage.
        """
        if stage == "fit" or stage is None:
            if self.train_file is not None:
                self.data_train = HDFSDataset(data_path=self.train_file,window_size=self.window_size)
            else: 
                self.data_train = None
            
            if self.val_file is not None:
                self.data_val = HDFSDataset(data_path=self.val_file,window_size=self.window_size)
            else: 
                self.data_val = None


        if stage == "test" or stage is None:
            if self.test_file is not None:
                # self.data_test = HDFSTestDataset(data_path=self.test_file,window_size=self.window_size)
                self.data_test = HDFSDataset(data_path=self.test_file,window_size=self.window_size)
            else:
                self.data_test = None

        
    @override
    def train_dataloader(self):
        if self.data_train is None:
            logm.console.log("Training data not found.")
            raise ValueError("Training data not found.")
        return DataLoader(self.data_train, batch_size=self.batch_size,shuffle=True)
    
    @override
    def test_dataloader(self):
        if self.data_test is None:
            logm.console.log("Test data not found.")
            raise ValueError("Test data not found.")
        return DataLoader(self.data_test, batch_size=len(self.data_test.sequences),shuffle=False)
    
    @override
    def val_dataloader(self):
        if self.data_val is None:
            logm.console.log("Validation data not found.")
            raise ValueError("Validation data not found.")
        return DataLoader(self.data_val, batch_size=self.batch_size, shuffle=False)

if __name__ == "__main__":

    module = HDFSDataModule(test_file='../datasets/hdfs_datasets/test.csv',batch_size=32,window_size=10)
    module.setup()
    for seq, pair in iter(module.test_dataloader()):
        print(seq,pair)
    
                           
    
