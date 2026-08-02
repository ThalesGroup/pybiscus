from typing import override, Optional, Tuple

import numpy as np
import lightning.pytorch as pl
import torchvision.transforms as transforms

from torch.utils.data import DataLoader, Subset
from torchvision.datasets import CIFAR10

import pybiscus.core.pybiscus_logger as logm
import argparse
import random

import glob
import os
from torch.utils.data import Dataset
import torch
import torchvision.transforms as transforms
from torchvision.tv_tensors import BoundingBoxes

from PIL import Image
import random
from pathlib import Path
from collections import defaultdict

import pandas as pd


IMG_SIZE = (300, 350)  # The image size
DISPLAY_PERIOD = 100  # The number iterations to go to display the results
MASK_THRESHOLD = 0.1  # The threshold to use to build the binary masks (Unet model outputs), small value => more white in the mask
NORMALIZATION_PARAMS = [
    (0.485, 0.456, 0.406),
    (0.229, 0.224, 0.225),
]  # the values to normalize images before feeding the model
IMG_SHAPE = (600, 700)
IMG_SIZE = IMG_SHAPE[0] * IMG_SHAPE[1]
REWEIGHT_IMPORTANCE = 0.7


class iSAIDLightningDataModule(pl.LightningDataModule):
    """
    A LightningDataModule is an abstract class provided by PyTorch Lightning
    that simplifies data management in machine learning workflows.
    It helps structure code by separating data preparation logic from the model training logic,
    making the code more modular and reusable.

    Role:

        1) Data Encapsulation:

           * Centralizes data loading and preparation logic,
           separating these concerns from the model training logic.

        2) Reusability:

            * Facilitates the reuse of data management code across different projects or experiments.

        3) Integration with PyTorch Lightning:

            * Seamlessly integrates with other PyTorch Lightning components, i
            such as the Trainer, to automate training and evaluation processes.

    API:

        1) __init__(self, *args, **kwargs)

            * Description:
                Initializes the data module with necessary parameters, such as data paths, batch size, etc.

            * Parameters:
                *args, **kwargs: Application-specific parameters, such as
                data paths, batch size, number of workers, etc.

        2) prepare_data(self)

            * Description:
                Used to download data if necessary.
                This method is called only once per node, which is useful for downloading data across multiple nodes.

        3) setup(self, stage: Optional[str] = None)

            * Description:
                Prepares datasets for different stages (training, validation, testing).

            * Parameters:
                stage: Current stage ("fit" for training and validation, "test" for testing, or None for all stages).

        4) train_dataloader(self) -> DataLoader

            * Description:
                Returns a DataLoader for the training dataset.

        5) val_dataloader(self) -> DataLoader

            * Description:
                Returns a DataLoader for the validation dataset.

        6) test_dataloader(self) -> DataLoader

            * Description:
                Returns a DataLoader for the test dataset.

        7) teardown(self, stage: Optional[str] = None)

            * Description:
                Used to clean up resources after a stage has run, such as deleting temporary files.

            * Parameters:
                stage: Current stage ("fit", "test", or None).

     ----------------------------------

    torch.utils.data.DataLoader is a crucial component in PyTorch for efficiently loading and iterating over datasets.
    It provides an iterable over a given dataset, enabling easy access to data samples,
    batching, shuffling, and parallel data loading.

    Purpose of DataLoader

        1) Batching:

            Automatically groups data samples into batches,
            which is essential for training machine learning models efficiently.

        2) Shuffling:

            Randomly shuffles the data at each epoch, which helps in training models
            by preventing them from learning the order of the data.

        3) Parallel Data Loading:

            Utilizes multiple subprocesses to load data in parallel,
            which can significantly speed up the data loading process, especially for large datasets.

        4) Customization:

            Allows customization of data loading behavior through various parameters and custom collate functions.

    Key Features and Parameters

        1) dataset (Dataset):

            The dataset from which to load the data. It should be an instance of a torch.utils.data.Dataset or a subclass.

        2) batch_size (int, optional):

            The number of samples per batch to load.
            Default is 1.

        3) shuffle (bool, optional):

            If True, data is reshuffled at every epoch.
            Default is False.

        4) num_workers (int, optional):

            The number of subprocesses to use for data loading. 0 means that the data will be loaded in the main process.
            Default is 0.

        5) collate_fn (callable, optional):

            Merges a list of samples to form a mini-batch of Tensor(s).
            Used when samples are of varying sizes or types.

        6) drop_last (bool, optional):

            If True, the last batch is dropped if it is smaller than batch_size.
            Default is False.

     ----------------------------------

     The torch.utils.data.Dataset class in PyTorch is an abstract class representing a dataset.
     It provides a way to access data samples and their corresponding labels,
     making it a fundamental component for loading and iterating over data in PyTorch.

    Purpose:

        * Data Abstraction:

            Provides a consistent interface for accessing data samples and their corresponding labels.

        * Customization:

            Allows for the creation of custom datasets by subclassing and implementing specific methods.

    Key Methods:

        1) __len__(self)

            Description:
                Returns an integer representing the size of the dataset.

        2) __getitem__(self, index)

            Description:
                Retrieves the sample and its corresponding label at the given index.
                The format can vary depending on the dataset (e.g., a tuple of tensor(s)).

    """

    @override
    def __init__(
        self,
        dir_train,
        data_train_indices_path,
        dir_val,
        data_val_indices_path,
        dir_test,
        batch_size,
        mode : str = "Detection",
        img_size: Tuple[int] = (300, 350),
        num_workers: int = 0,
        label_dict: dict = None
    ):

        super().__init__()

        # init parameters memo
        self.data_dir_train = dir_train
        self.data_train_indices_path = data_train_indices_path
        self.data_dir_val = dir_val
        self.data_val_indices_path = data_val_indices_path
        self.img_size = img_size
        # self.data_dir_val   = dir_val
        self.data_dir_test = dir_test
        self.num_workers = num_workers
        self.batch_size = batch_size
        self.mode = mode
        self.label_dict = label_dict
        self.collate_fn=None
        if self.mode == "Detection":
            self.collate_fn=collate_detection()
        

        # DataLoaders for train, val and test phasis
        self.data_train = None
        self.data_val = None
        self.data_test = None

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
            if self.mode == "Detection":
                isaid_train = iSAIDDetectionDataset(
                    data_path=self.data_dir_train,
                    label_dict=self.label_dict
                )
                isaid_val = iSAIDDetectionDataset(
                    data_path=self.data_dir_val,
                    label_dict=self.label_dict
                )
            else:
                isaid_train = iSAIDImageDataset(
                    path=self.data_dir_train,
                    img_size = self.img_size, 
                    mask_threshold = 0.1,
                    augmentation=True
                )
                isaid_val = iSAIDImageDataset(
                    path=self.data_dir_val,
                    img_size = self.img_size, 
                    mask_threshold = 0.1,
                    augmentation=True
                )
            if self.data_train_indices_path is None:
                self.data_train = isaid_train
                logm.console.log("data train size: ", len(self.data_train.indices))

            else:
                data_train_indices = self._read_file_indices(
                    self.data_train_indices_path
                )
                self.data_train = Subset(isaid_train, data_train_indices)
                logm.console.log("data train size: ", len(self.data_train.indices))

            if self.data_val_indices_path is None:
                self.data_val = isaid_val
                logm.console.log("data val size: ", len(self.data_val.indices))
            else:
                data_val_indices = self._read_file_indices(self.data_val_indices_path)
                self.data_val = Subset(isaid_val, data_val_indices)
                logm.console.log("data val size: ", len(self.data_val.indices))

        if stage == "test" or stage is None:
            if self.mode == "Detection":
                self.data_test = iSAIDDetectionDataset(
                    data_path=self.data_dir_test,
                    label_dict=self.label_dict
                )
            else:
                self.data_test = iSAIDImageDataset(
                    path=self.data_dir_test,
                    img_size = self.img_size, 
                    mask_threshold = 0.1,
                    augmentation=False,
                )
            logm.console.log("data test shape", len(self.data_test.indices))

    def _read_file_indices(self, filepath):
        """
        Return a list containing all integers seperated with whitespaces present in the file
        """
        list_indices = []
        with open(filepath, "r") as file:
            for line in file:
                for d in line.strip().split():
                    if d.isdigit():
                        list_indices.append(int(d))
        return list_indices

    @override
    def train_dataloader(self) -> DataLoader:

        if self.data_train is None:
            raise ValueError("Train dataset undefined: bad setup")

        return DataLoader(
            self.data_train,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            drop_last=True,
            shuffle=True,
            collate_fn=self.collate_fn
        )

    @override
    def val_dataloader(self) -> DataLoader:

        if self.data_val is None:
            raise ValueError("Val dataset undefined: bad setup")

        return DataLoader(
            self.data_val,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            drop_last=True,
            shuffle=False,
            collate_fn=self.collate_fn
        )

    @override
    def test_dataloader(self) -> DataLoader:

        if self.data_test is None:
            raise ValueError("Test dataset undefined: bad setup")

        return DataLoader(
            self.data_test,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            drop_last=False,
            shuffle=False,
            collate_fn=self.collate_fn
        )


def write_list_to_file(list_indices, output_path):
    L = [f"{d}\n" for d in list_indices]
    with open(output_path, "w") as fp:
        fp.writelines(L)


class iSAIDDetectionDataset(Dataset):
    """
    TODO
    """

    def __init__(
        self, data_path , label_dict=None
    ) -> None:
        """
        Supposes that the data is organised in subfolder, one subfolder per class.
        class_name are all three digit integer, example:
        train/
        -----images/
        -----------/000_A/ then plenty of .png files
        -----------/234_B/ then plenty of .png files
        -----------/236_A/ then plenty of .png files
        -----BB/
        -----------/000_A/ then plenty of .csv files
        -----------/234_B/ then plenty of .csv files
        -----------/236_A/ then plenty of .csv files
        """
        super().__init__()
        self.data_path = data_path
        self.list_images = [str(p) for p in Path(f"{data_path}/images/").rglob("*.png")]
        self.indices = [i for i in range(len(self.list_images))]
        all_classes = list(set([0]+[int(img.split("/")[-2][-5:-2]) for img in self.list_images]))
        all_classes.sort()
        if label_dict is None:
            self.label_dict = {
                idx: class_name for idx, class_name in enumerate(all_classes)
            }
            self.label_dict_rev = {
                class_name: idx for idx, class_name in enumerate(all_classes)
            }
        else:
            self.label_dict = label_dict
            self.label_dict_rev = {v: k for k, v in label_dict.items()}
        self.transforms = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    def __len__(self):
        return len(self.list_images)

    def get_label_dics(self):
        return self.label_dict, self.label_dict_rev

    def get_boxes_from_png(self, png_path, nb_lines, nb_columns):
        csv_path = png_path.replace("/images/", "/BB/")[:-3] + "csv"
        image_id = png_path.split("/")[-1].split(".")[0]
        target = {}
        boxes = []
        labels = []
        try:
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                if row["X1"]<=row["X0"]:
                    continue
                if row["Y1"]<=row["Y0"]:
                    continue
                boxes.append(
                    [
                        
                        int(row["X0"]),
                        int(row["Y0"]),
                        int(row["X1"]),
                        int(row["Y1"]),
                        
                    ]
                )
                labels.append(int(self.label_dict_rev[int(row["class"])]))
        except pd.errors.EmptyDataError as err:
            print(f"EmptyDataError {err}")
        if len(boxes) == 0:
            boxes.append([0, 0, nb_columns, nb_lines])
            labels.append(0)
        target["boxes"] = BoundingBoxes(
            boxes, format="XYXY", canvas_size=(nb_columns, nb_lines)
        )
        target["labels"] = torch.tensor(labels, dtype=torch.int64)
        target["image_id"] = image_id

        if len(boxes) > 0:
            target["area"] = torch.Tensor(
                [(box[3] - box[1]) * (box[2] - box[0]) for box in target["boxes"]]
            )
        else:
            target["area"] = torch.Tensor([0])
        target["iscrowd"] = torch.zeros((len(boxes),), dtype=torch.int64)
        return target

    def __getitem__(self, index) -> Tuple:
        png_path = self.list_images[index]
        img = Image.open(png_path).convert("RGB") # 
        width, height = img.size
        target = self.get_boxes_from_png(png_path, nb_lines=height, nb_columns=width)
        if self.transforms:
            img = self.transforms(img)
        _, height, width = img.shape
        mask = torch.zeros((height, width), dtype=torch.long)
        for box, label in zip(target["boxes"], target["labels"]):
            x1, y1, x2, y2 = box.int()
            mask[y1:y2, x1:x2] = label.long()
        target["mask"] = mask
        return img, target

class collate_detection:
    def __call__(self, batch):
        data = [item[0] for item in batch]
        targets = [item[1] for item in batch]
        if len(data) > 1:
            data = torch.stack(data)
        else : data = data[0].unsqueeze(0)
        return data, targets



class iSAIDImageDataset(Dataset):
    def __init__(self, path, augmentation, img_size=(300, 350), mask_threshold=0.1):

        self.img_dir = path
        self.image_list = []
        self.mask_threshold = mask_threshold

        # iSAID
        img_format = "png"
        self.label_suffix = "_instance_color_RGB.png"

        # keep only images with labels
        labels_paths = glob.glob(path + "/label/*." + img_format)
        labels_files_names = [
            filepath.split("/")[-1][: -len(img_format) - 1] for filepath in labels_paths
        ]
        all_paths = glob.glob(path + "/image/*." + img_format)

        for filepath in all_paths:

            try:
                # Image.open(filepath).convert("RGB") #try to open it. Do not add it if corrupt => slow

                img_filename = filepath.split("/")[-1]

                if img_filename[: -len(img_format) - 1] in labels_files_names:
                    self.image_list.append(img_filename)
            except:
                print(f"Warning: File {filepath} is corrupt and could not be opened !")
        self.indices = [i for i in range(len(self.image_list))]
        print(f"The total number of found files in {path} is: {len(all_paths)}")
        print(
            f"The number of validated images/labels from {path} is {len(self.image_list)}"
        )

        # apply transforms after loading an image
        self.transform_img = transforms.Compose(
            [
                transforms.Resize(img_size),
                transforms.ToTensor(),
                transforms.Normalize(NORMALIZATION_PARAMS[0], NORMALIZATION_PARAMS[1]),
            ]
        )

        self.transform_mask = transforms.Compose(
            [
                transforms.Grayscale(num_output_channels=1),
                transforms.Resize(img_size),
                transforms.ToTensor(),
            ]
        )

        self.augmentation = augmentation

    def __len__(self):
        return len(self.image_list)

    def __getitem__(self, idx):

        img_path = self.img_dir + "/image/" + self.image_list[idx]

        mask_path = self.img_dir + "/label/" + self.image_list[idx]

        image = Image.open(img_path).convert("RGB")

        mask = Image.open(mask_path)

        if self.augmentation:

            if random.random() < 0.5:
                image = transforms.functional.hflip(image)
                mask = transforms.functional.hflip(mask)

            if random.random() < 0.5:
                image = transforms.functional.vflip(image)
                mask = transforms.functional.vflip(mask)

            if random.random() < 0.5:
                degree = random.randint(0, 360)
                image = transforms.functional.rotate(
                    image,
                    angle=degree,
                    interpolation=transforms.InterpolationMode.NEAREST,
                )
                mask = transforms.functional.rotate(
                    mask,
                    angle=degree,
                    interpolation=transforms.InterpolationMode.NEAREST,
                )

        mask = self.transform_mask(mask)
        mask = torch.where(mask >= self.mask_threshold, 1, 0)
        mask = mask.squeeze(0)

        return self.transform_img(image), mask.float()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Create Non overlapping datasets for Federated Learning"
    )
    parser.add_argument(
        "--nb_clients", type=int, required=True, help="Nombre de clients"
    )
    parser.add_argument(
        "--approach", type=str, required=True, help="Approach to divide by client. RANDOM or BYNAME"
    )
    parser.add_argument(
        "--data_path",
        type=str,
        required=True,
        help="Path to the root dataset that is splitted",
    )
    parser.add_argument(
        "--output_folder",
        type=str,
        required=True,
        help="Path to where the indices list will be stored",
    )

    args = parser.parse_args()

    isaid_dataset = iSAIDDetectionDataset(
                data_path=f"{args.data_path}"
            )
    if args.approach=="RANDOM":
        shuffled_indices = [i for i in range(len(isaid_dataset))]
        random.shuffle(shuffled_indices)

        nb_indices_client = int(len(shuffled_indices) / args.nb_clients)

        for client in range(args.nb_clients):
            client_indices = shuffled_indices[
                client * nb_indices_client : (client + 1) * nb_indices_client
            ]
            write_list_to_file(
                client_indices[:int(len(client_indices)*0.8)], 
                f"{args.output_folder}/client_{client}_train.txt"
            )
            write_list_to_file(
                client_indices[int(len(client_indices)*0.8):], 
                f"{args.output_folder}/client_{client}_val.txt"
            )
    else:
        list_images = isaid_dataset.list_images
        clients_dic = defaultdict(lambda: defaultdict(list))
        print(list_images[:10])
        print(list_images[-10:])
        print(len(list_images))
        for idx, img_path in enumerate(list_images):
            subfolder_name = img_path.split('/')[-2]
            client_name = subfolder_name.split('_')[-1]
            split = subfolder_name.split('_')[0]
            clients_dic[client_name][split].append(idx)

        print(f"We found {len(clients_dic.keys())} different client names")

        for client_name, split_indices in clients_dic.items():
            for split_name, image_indices in split_indices.items():
                write_list_to_file(
                    image_indices,
                    f"{args.output_folder}/client_{client_name}_{split_name}.txt",
                )
