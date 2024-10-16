from torch.utils.data import Dataset
import pandas as pd

# Example taken from https://www.kaggle.com/code/jinsolkwon/rul-predictions-using-pytorch-lstm#1.-Data-Processing


class turbofan_dataset(Dataset):
    def __init__(self, engines_list, window=20, datapath="turbofan.txt"):
        df = pd.read_csv(datapath, sep=",")
        df = df.dropna(axis=1)
        self.df = df[df.engine_no.isin(engines_list)].__deepcopy__()
        self.add_rul()
        self.window = window

    def __len__(self):
        return len(self.df) - self.window

    def __getitem__(self, idx):
        X = (
            self.df.iloc[idx : idx + self.window, :]
            .drop(["time_in_cycles", "engine_no", "rul"], axis=1)
            .copy()
            .to_numpy()
        )
        y = self.df.iloc[idx + self.window - 1]["rul"]
        return X, y

    def add_rul(self):
        """Add remaining useful lifetime values, the value we want to be able to predict"""
        tot_time = {}
        for engine in self.df.engine_no.unique():
            df_engine = self.df[self.df.engine_no == engine]
            tot_time[engine] = len(df_engine)
        self.df["rul"] = self.df[["engine_no", "time_in_cycles"]].apply(
            lambda x: tot_time[x.iloc[0]] - x.iloc[1], axis=1
        )