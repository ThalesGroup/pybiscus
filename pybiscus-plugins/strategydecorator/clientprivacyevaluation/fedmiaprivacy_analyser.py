# Todo provide attack code over the iteration => call it at each iteration (taking into account the previous ones and this iteration alone) (0.5j)
# Todo adapt UNet / FasterRCNN with ISAID dataset on multi class dataset but with only one class per image (1.5j)

from typing import Tuple

import numpy as np
import os


import pandas as pd
from sklearn.metrics import roc_curve, auc
import matplotlib.pyplot as plt


def analyse_mia_infos(round_path):
    client_split_path: str = (None,)  # path to the folder containing the ground truth
    round_path: str = (
        None,
    )  # path to the folder containing the info saved at each round;
    fpr_threshold: float = (0.01,)
    log_scale_roc: bool = (True,)
    client_label_mapping: Optional[dict[str, str]] = (None,)
    filter_class_000_in_roc: bool = (False,)
    show_boxplot_outliers: bool = (False,)
    scatter_class_filter: Optional[list[str]] = (None,)


def process_cosine_df(df_cosine):
    cid_cols = [col for col in df_cosine.columns if col not in ["Image_idx", "round"]]
    df_stat = pd.DataFrame(
        {
            "mean": df_cosine[cid_cols].mean(axis=1),
            "median": df_cosine[cid_cols].median(axis=1),
            "std": df_cosine[cid_cols].std(axis=1),
            "min": df_cosine[cid_cols].min(axis=1),
            "max": df_cosine[cid_cols].max(axis=1),
            "cid_max": df_cosine[cid_cols].idxmax(axis=1),
            "IQR": df_cosine[cid_cols].quantile(0.75, axis=1)
            - df_cosine[cid_cols].quantile(0.25, axis=1),
            "Q1": df_cosine[cid_cols].quantile(0.25, axis=1),
            "Q3": df_cosine[cid_cols].quantile(0.75, axis=1),
        }
    )

    for col in df_stat.columns:
        df_cosine[col] = df_stat[col]

    df_cosine["lower_whisker"] = df_cosine["Q1"] - 1.5 * df_cosine["IQR"]
    df_cosine["higher_whisker"] = df_cosine["Q3"] + 1.5 * df_cosine["IQR"]

    return df_cosine


def process_loss_df(df_loss, plot_path: str = ""):
    cid_cols_in_res = [
        col for col in df_loss.columns if col not in ["Image_idx", "round", "server_in"]
    ]
    cid_cols = []
    for col in cid_cols_in_res:
        cid_name = col.split("_")[0]
        if cid_name not in cid_cols:
            cid_cols.append(cid_name)
    print("cid_cols", cid_cols)
    for cid_name in cid_cols:
        df_loss[cid_name] = df_loss[f"{cid_name}_in"] - df_loss[f"{cid_name}_res"]
    df_stat = pd.DataFrame(
        {
            "mean": df_loss[cid_cols].mean(axis=1),
            "median": df_loss[cid_cols].median(axis=1),
            "std": df_loss[cid_cols].std(axis=1),
            "min": df_loss[cid_cols].min(axis=1),
            "max": df_loss[cid_cols].max(axis=1),
            "cid_max": df_loss[cid_cols].idxmax(axis=1),
            "IQR": df_loss[cid_cols].quantile(0.75, axis=1)
            - df_loss[cid_cols].quantile(0.25, axis=1),
            "Q1": df_loss[cid_cols].quantile(0.25, axis=1),
            "Q3": df_loss[cid_cols].quantile(0.75, axis=1),
        }
    )

    for col in df_stat.columns:
        df_loss[col] = df_stat[col]

    df_loss["lower_whisker"] = df_loss["Q1"] - 1.5 * df_loss["IQR"]
    df_loss["higher_whisker"] = df_loss["Q3"] + 1.5 * df_loss["IQR"]

    return df_loss


def make_attack_plot(df, plot_path):

    print(df[df["max"] >= df["higher_whisker"]].shape)
    unique_cids = df["cid_max"].unique()
    print(df.head())
    for round in df["round"].unique():
        # Plot histogram for each cid_max
        plt.hist(
            [
                df[df["round"]==round][cid]
                for cid in unique_cids
            ],
            bins=10,
            label=unique_cids,
            alpha=0.7,  # Transparency
            stacked=False,  # Set to False for side-by-side bars
        )

        plt.legend(title="Values per cid")
        plt.xlabel("count")
        plt.ylabel("Frequency")
        plt.title("Histogram of values per cid")
        plt.savefig(f"{plot_path}_round_{round}.png")
        plt.close()

    df_plot_hist_count = (
        df.groupby(["cid_max", "Image_idx"])
        .count()
        .reset_index()[["cid_max", "Image_idx", "round"]]
    )
    df_plot_hist_count["count"] = df_plot_hist_count["round"]

    # Get unique cid_max values
    unique_cids = df_plot_hist_count["cid_max"].unique()

    # Plot histogram for each cid_max
    plt.hist(
        [
            df_plot_hist_count[df_plot_hist_count["cid_max"] == cid]["count"]
            for cid in unique_cids
        ],
        bins=10,
        label=unique_cids,
        alpha=0.7,  # Transparency
        stacked=False,  # Set to False for side-by-side bars
    )

    plt.legend(title="cid_max")
    plt.xlabel("count")
    plt.ylabel("Frequency")
    plt.title("Histogram of count by cid_max")
    plt.savefig(f"{plot_path}.png")
    plt.close()

    print(df_plot_hist_count["count"].max())
    print(
        df_plot_hist_count[
            df_plot_hist_count["count"] == df_plot_hist_count["count"].max()
        ].shape
    )
    # return the id of images that got the highest count
    img_id = df_plot_hist_count[
        df_plot_hist_count["count"] == df_plot_hist_count["count"].max()
    ]["Image_idx"].tolist()
    return img_id


def get_dataframes(
    round_path: str,
    cosine_file_name: str,
    loss_file_name: str,
    plot_folder: str,
) -> Tuple[list[pd.DataFrame], list[pd.DataFrame], list[str], list[int], list[int]]:
    """Boxplot de la similarité cosinus par classe et par client."""
    df_cosine_list = []
    df_loss_list = []
    for subfolder in os.listdir(round_path):
        if os.path.isdir(f"{round_path}/{subfolder}"):
            round_num = subfolder.split("_")[-1]
            if round_num.isdigit():
                round_num = int(round_num)
                for file in os.listdir(f"{round_path}/{subfolder}"):
                    if file == cosine_file_name:
                        df_cosine = pd.read_csv(
                            f"{round_path}/{subfolder}/{cosine_file_name}"
                        )
                        df_cosine["round"] = round_num
                        df_cosine_list.append(df_cosine)
                    if file == loss_file_name:
                        df_loss = pd.read_csv(
                            f"{round_path}/{subfolder}/{loss_file_name}"
                        )
                        df_loss["round"] = round_num
                        df_loss_list.append(df_loss)
                print(round_num, df_loss.shape, df_cosine.shape)
    df_loss = pd.concat(df_loss_list)
    df_cosine = pd.concat(df_cosine_list)

    print(df_loss.shape, df_cosine.shape)

    cid_cols = [col for col in df_cosine.columns if col not in ["Image_idx", "round"]]

    df_cosine_random = pd.DataFrame(
        np.random.rand(len(df_cosine), len(cid_cols)),
        columns=cid_cols,
        index=df_cosine.index,
    )
    df_loss_random = pd.DataFrame(
        np.random.rand(len(df_loss), len(cid_cols)),
        columns=cid_cols,
        index=df_loss.index,
    )

    # loop through the other cosine columns
    # df_loss contains other columns that are not of interest for simu cid_res, cid_in, we rather randomize directly the difference
    for col in df_cosine.columns:
        if col not in cid_cols:
            print(col)
            df_cosine_random[col] = df_cosine[col]
            df_loss_random[col] = df_loss[col]

    df_cosine = process_cosine_df(df_cosine)
    df_loss = process_loss_df(df_loss)

    img_id_cosine = make_attack_plot(
        df_cosine, plot_path=f"{plot_folder}/pred_attack_cosine_hist"
    )
    img_id_loss = make_attack_plot(
        df_loss, plot_path=f"{plot_folder}/pred_attack_loss_hist"
    )

    intersection_count = 0
    for img in img_id_loss:
        if img in img_id_cosine:
            intersection_count += 1
    print(
        "cosine and loss intersection size",
        intersection_count,
        len(img_id_cosine),
        len(img_id_loss),
    )

    df_cosine_random = process_cosine_df(df_cosine_random)
    img_id_cosine_random = make_attack_plot(
        df_cosine_random, plot_path=f"{plot_folder}/random_pred_attack_cosine_hist"
    )
    df_loss_random = process_cosine_df(df_loss_random)
    img_id_loss_random = make_attack_plot(
        df_loss_random, plot_path=f"{plot_folder}/random_pred_attack_loss_hist"
    )

    intersection_count = 0
    for img in img_id_loss_random:
        if img in img_id_cosine_random:
            intersection_count += 1
    print(
        "random intersection size",
        intersection_count,
        len(img_id_cosine_random),
        len(img_id_loss_random),
    )
    df_cosine.to_csv(f"{plot_folder}/df_cosine.csv", index_label="Image_idx")
    df_loss.to_csv(f"{plot_folder}/df_loss.csv", index_label="Image_idx")
    return df_cosine, df_loss, cid_cols, img_id_cosine, img_id_loss


def get_groundtruth_dataframes(
    data_split_path: str,
    save_folder: str,
    dic_client_name: dict = None,
    data_split_list_path: list[str] = None
) -> pd.DataFrame:
    gt_data = []
    if data_split_list_path is None:
        data_split_list_path = [file for file in os.listdir(f"{data_split_path}")]
    for file in data_split_list_path:
        filename = file.split('/')[-1]
        _, client_num, split = filename.split("_")
        if dic_client_name is not None:
            client_num = dic_client_name[client_num]
        with open(f"{data_split_path}/{filename}", "r") as file:
            for line in file:
                for d in line.strip().split():
                    if d.isdigit():
                        gt_data.append(
                            {
                                "Image_idx": int(d),
                                "client_num": int(client_num),
                                "split": split.split(".")[0],
                            }
                        )
    df_gt = pd.DataFrame.from_records(gt_data, index="Image_idx")
    df_gt.to_csv(f"{save_folder}/ground_truth.csv", index_label="Image_idx")
    return df_gt.reset_index()


def plot_binary_ROCs(df_attack, df_gt, cid_list, plot_title, plot_path, round_num=-1):
    """
        We use as prediction value for each client, each data, each round : 
        1 if the client as the max value of the cosine, 0 otherwise
        Pro : exactly one client is predicted to own each data
        Con : ROC curve have very few points
        """
    print(round_num, type(round_num))
    for client_num, client in enumerate(cid_list):
        df_gt.sort_values("Image_idx", inplace=True)
        if round_num >= 0:
            df_attack = df_attack[df_attack["round"] == round_num]
        print(df_gt)
        print(client_num)
        print(df_gt[(df_gt["client_num"] == client_num) & (df_gt["split"] == "train")])
        train_truth = df_gt[
            (df_gt["client_num"] == client_num) & (df_gt["split"] == "train")
        ]["Image_idx"].tolist()
        y_true = df_gt["Image_idx"].apply(lambda x: 1 if x in train_truth else 0).values
        df_attack[f"{client}_pred"] = df_attack["cid_max"].apply(
            lambda x: 1 if x == client else 0
        )
        y_pred = (
            df_attack[["Image_idx", f"{client}_pred"]]
            .groupby("Image_idx")
            .mean()
            .reset_index()[f"{client}_pred"]
            .values
        )
        y_pred_bin = np.array([1 if p > 0.5 else 0 for p in y_pred])
        print(len(train_truth), len(y_true), len(y_pred))
        print(
            client_num,
            client,
            (y_pred_bin == y_true).sum(),
            y_pred_bin.sum(),
            y_true.sum(),
        )
        good_pred = 0
        for p, gt in zip(y_pred_bin, y_true):
            if (gt == 1) and (p == 1):
                good_pred += 1
        print(good_pred)
        # Compute ROC curve
        fpr, tpr, thresholds = roc_curve(y_true, y_pred)
        roc_auc = auc(fpr, tpr)
        print(len(y_true),len(y_pred))
        print(plot_title, client,"fpr",fpr)
        print(plot_title, client,"tpr",tpr)
        print(plot_title, client,"thresholds", thresholds)
        # Plot
        plt.figure()
        plt.plot(
            fpr, tpr, color="darkorange", lw=2, label=f"ROC curve (AUC = {roc_auc:.2f})"
        )
        plt.plot([0, 1], [0, 1], "k--")
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title(f"Client {client_num} {client} {plot_title}")
        plt.legend(loc="lower right")
        plt.savefig(f"{plot_path}_{client}.png")
        plt.close()

def get_tpr_at_frp(tpr_list, fpr_list, fpr_aim):
    for th_idx, fpr_value in enumerate(fpr_list):
        if fpr_value < fpr_aim:
            continue
        else:
            return tpr_list[th_idx].item(), fpr_list[th_idx].item(), (tpr_list[th_idx]/fpr_list[th_idx]).item()
    return 1, 1

def plot_ROCs(df_attack, df_gt, cid_list, plot_title, plot_path, round_num=-1):
    """
    We use as prediction value for each client, each data, each round : 
    the cosine of the client minus the median cosine of the all the clients
    """
    for client_num, client in enumerate(cid_list):
        df_gt.sort_values("Image_idx", inplace=True)
        if round_num >= 0:
            df_attack = df_attack[df_attack["round"] == round_num]
        train_truth = df_gt[
            (df_gt["client_num"] == client_num) & (df_gt["split"] == "train")
        ]["Image_idx"].tolist()
        y_true = df_gt["Image_idx"].apply(lambda x: 1 if x in train_truth else 0).values
        df_attack[f"{client}_pred"] = df_attack[[client, "median"]].apply(
            lambda x: x[client]-x["median"], axis=1
        )
        y_pred = (
            df_attack[["Image_idx", f"{client}_pred"]]
            .groupby("Image_idx")
            .mean()
            .reset_index()[f"{client}_pred"]
            .values
        )
        y_pred_bin = np.array([1 if p > 0 else 0 for p in y_pred])
        print(
            client_num,
            client,
            (y_pred_bin == y_true).sum(),
            y_pred_bin.sum(),
            y_true.sum(),
        )
        good_pred = 0
        for p, gt in zip(y_pred_bin, y_true):
            if (gt == 1) and (p == 1):
                good_pred += 1
        print("nb of correct true prediction", good_pred)
        # Compute ROC curve
        fpr, tpr, thresholds = roc_curve(y_true, y_pred)
        roc_auc = auc(fpr, tpr)
        print(f"Client {client_num} {client} {plot_title} round {round_num}")
        print("TPR@FPR 10-3", "(tpr, fpr, ratio)", get_tpr_at_frp(tpr, fpr, 0.001))
        print("TPR@FPR 10-2", "(tpr, fpr, ratio)", get_tpr_at_frp(tpr, fpr, 0.01))
        print("TPR@FPR 10-1", "(tpr, fpr, ratio)", get_tpr_at_frp(tpr, fpr, 0.1))
        # Plot
        plt.figure()
        plt.plot(
            fpr, tpr, color="darkorange", lw=2, label=f"ROC curve (AUC = {roc_auc:.2f})"
        )
        plt.plot([0, 1], [0, 1], "k--")
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title(f"Client {client_num} {client} {plot_title}")
        plt.legend(loc="lower right")
        plt.savefig(f"{plot_path}_{client}.png")
        plt.close()


if __name__ == "__main__":

    round_path = "../../../experiments/current/rounds"
    round_path = "../../../experiments/2026-07-31T15:33:34.975139/rounds"
    df_cosine, df_loss, cid_list, img_cos_selected, img_loss_selected = get_dataframes(
        round_path=round_path,
        cosine_file_name="cosine_matrix.csv",
        loss_file_name="loss_per_instances.csv",
        plot_folder="plots/",
    )
    ground_truth_folder = "../../../datasets/cifar10/2clients_splits/"
    ground_truth_folder = "../../../datasets/iSAID/1category_per_image/spectro_like_50/2clients_trainval_splits"
    df_gt = get_groundtruth_dataframes(
        data_split_path=ground_truth_folder,
        save_folder="plots/",
        dic_client_name={"A": 0,"B": 1},
    )

    plot_ROCs(
        df_attack=df_cosine,
        df_gt=df_gt,
        cid_list=cid_list,
        plot_title="ROC Curve cosine",
        plot_path="plots/ROC_cosine_all",
    )

    plot_ROCs(
        df_attack=df_loss,
        df_gt=df_gt,
        cid_list=cid_list,
        plot_title="ROC Curve loss",
        plot_path="plots/ROC_loss_all",
    )
    for round_num in df_cosine["round"].unique():
        plot_ROCs(
            df_attack=df_cosine,
            df_gt=df_gt,
            cid_list=cid_list,
            plot_title="ROC Curve cosine",
            plot_path=f"plots/ROC_cosine_round_{round_num}",
            round_num=round_num,
        )

        plot_ROCs(
            df_attack=df_loss,
            df_gt=df_gt,
            cid_list=cid_list,
            plot_title="ROC Curve loss",
            plot_path=f"plots/ROC_loss_round_{round_num}",
            round_num=round_num,
        )
