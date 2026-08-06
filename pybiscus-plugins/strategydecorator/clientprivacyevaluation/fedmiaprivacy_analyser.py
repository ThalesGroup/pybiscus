from typing import Tuple
import numpy as np
import os
import re
from pathlib import Path
import pandas as pd
from sklearn.metrics import roc_curve, auc
import matplotlib.pyplot as plt

from jsonargparse import ArgumentParser


def parse_args():
    parser = ArgumentParser(description="Experiment configuration")
    
    parser.add_argument(
        "--approach",
        type=str,
        choices=["median", "higher_whisker", "none"],
        default="median",
        help="Value use to get the score attack.\\" \
            "median: client's value minus the median of all clients.\\" \
            "higher_whisker: client's value minus the higher_whisker of all clients.\\" \
            "none: client's value",
    )
    parser.add_argument(
        "--save-folder",
        type=str,
        default="plots",
        help="Folder where to save plots",
    )
    parser.add_argument(
        "--ground-truth-folder",
        type=str,
        default="../../../datasets/cifar10/2clients_splits/",
        help="Folder containing ground truth datasets/splits, list of indices per client and splits",
    )
    parser.add_argument(
        "--round-path",
        type=str,
        default="../../../experiments/current/rounds",
        help="Path to rounds directory",
    )
    # Dict: client name (string) -> cid (int)
    parser.add_argument(
        "--dic-client-name",
        type=dict,
        default={"0": 0, "1": 1},
        help="Dictionary mapping client name to cid. Example: '{A:0,B:1}'",
    )
    parser.add_argument(
            "--plot_per_label",
            type=bool,
            default=True,
            help="Plot ROC curve per label, can be done only if file ${ground_truth_folder}/index_to_label.csv exists and like each index to a label",
        )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to a YAML config file",
    )
    args = parser.parse_args()
    return args


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
            [df[df["round"] == round][cid] for cid in unique_cids],
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


def extract_ordered_clients(server_log_path: str):
    # from the privacy analyser we cannot deduce wich client is which.
    # however in the server logs the information is here
    # Example :
    # Source is flower => client_id = 91a83a4f620c45fa8c4f57732325a3d7
    # Source is metrics => cid = 1
    # Source is flower => client_id = 61565d1d253c4585807d5655afb4104b
    # Source is metrics => cid = 0
    # Means cid_list[0] should be equal to "61565d1d253c4585807d5655afb4104b"
    # Means cid_list[1] should be equal to "91a83a4f620c45fa8c4f57732325a3d7"
    CLIENT_RE = re.compile(r"Source is flower => client_id = (\w+)")
    CID_RE = re.compile(r"Source is metrics => cid = (\d+)")
    pending_client_id = None
    cid_to_client = {}
    server_log_text = open(server_log_path, "r", encoding="utf-8").read()
    for line in server_log_text.splitlines():
        m_client = CLIENT_RE.search(line)
        if m_client:
            pending_client_id = m_client.group(1)
            continue

        m_cid = CID_RE.search(line)
        if m_cid and pending_client_id is not None:
            cid = int(m_cid.group(1))
            cid_to_client[cid] = pending_client_id
            pending_client_id = None  # reset for next pair

    # ordered by cid
    return [cid_to_client[cid] for cid in sorted(cid_to_client.keys())]


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
    df_loss = pd.concat(df_loss_list)
    df_cosine = pd.concat(df_cosine_list)

    cid_cols = extract_ordered_clients(f"{Path(round_path).parent}/server_logs.txt")
    print("ordered cids", cid_cols)
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
    data_split_list_path: list[str] = None,
) -> pd.DataFrame:
    gt_data = []
    if data_split_list_path is None:
        data_split_list_path = [
            file for file in os.listdir(f"{data_split_path}") if file.endswith(".txt")
        ]
    print(data_split_list_path)
    for file in data_split_list_path:
        filename = file.split("/")[-1]
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


def get_tpr_at_frp(tpr_list, fpr_list, fpr_aim):
    for th_idx, fpr_value in enumerate(fpr_list):
        if fpr_value < fpr_aim:
            continue
        else:
            return (
                tpr_list[th_idx].item(),
                fpr_list[th_idx].item(),
                (tpr_list[th_idx] / fpr_list[th_idx]).item(),
            )
    return 1, 1


def get_y_pred(df_attack, client, approach):
    if approach == "median":
        df_attack[f"{client}_pred"] = df_attack[[client, "median"]].apply(
            lambda x: x[client] - x["median"], axis=1
        )
    elif approach == "higher_whisker":
        df_attack[f"{client}_pred"] = df_attack[[client, "higher_whisker"]].apply(
            lambda x: x[client] - x["higher_whisker"], axis=1
        )
    else:  # approach=="none":
        df_attack[f"{client}_pred"] = df_attack[client]
    y_pred = (
        df_attack[["Image_idx", f"{client}_pred"]]
        .groupby("Image_idx")
        .mean()
        .reset_index()[f"{client}_pred"]
        .values
    )
    y_pred_bin = np.array([1 if p > 0 else 0 for p in y_pred])
    return y_pred, y_pred_bin


def plot_ROCs_label(
    df_attack,
    df_gt,
    cid_list,
    plot_title,
    plot_path,
    df_labels,
    round_num=-1,
    approach="higher_whisker",
):

    df_gt_merged = df_gt.merge(df_labels, on="Image_idx")

    # All labels, sorted increasing
    all_labels = sorted(df_gt_merged["label"].unique())

    # Deterministic colormap: same label -> same color across clients and runs
    # changes automatically if >10 labels; still deterministic
    cmap = plt.get_cmap("tab10")
    label_to_color = {lab: cmap(i % cmap.N) for i, lab in enumerate(all_labels)}

    for client_num, client in enumerate(cid_list):

        # ---------- LINEAR ROC (1 figure per client) ----------
        plt.figure(figsize=(7, 6))
        ax = plt.gca()

        for label in all_labels:
            df_gt_label = df_gt_merged[df_gt_merged["label"] == label].copy()
            df_gt_label.sort_values("Image_idx", inplace=True)
            indices_label = df_gt_label["Image_idx"].tolist()

            df_attack_label = df_attack
            if round_num >= 0:
                df_attack_label = df_attack_label[df_attack_label["round"] == round_num]
            df_attack_label = df_attack_label[
                df_attack_label["Image_idx"].isin(indices_label)
            ]

            train_truth = df_gt_label[
                (df_gt_label["client_num"] == client_num)
                & (df_gt_label["split"] == "train")
            ]["Image_idx"].tolist()

            y_true = (
                df_gt_label["Image_idx"]
                .apply(lambda x: 1 if x in train_truth else 0)
                .values
            )
            y_pred, y_pred_bin = get_y_pred(df_attack_label, client, approach)

            print(
                client_num,
                client,
                (y_pred_bin == y_true).sum(),
                y_pred_bin.sum(),
                y_true.sum(),
                "label=",
                label,
            )

            # ROC
            fpr, tpr, _ = roc_curve(y_true, y_pred)
            roc_auc = auc(fpr, tpr)

            print(
                f"Client {client_num} {client} {plot_title} round {round_num} label {label}"
            )
            print("TPR@FPR 10-3", "(tpr, fpr, ratio)", get_tpr_at_frp(tpr, fpr, 0.001))
            print("TPR@FPR 10-2", "(tpr, fpr, ratio)", get_tpr_at_frp(tpr, fpr, 0.01))
            print("TPR@FPR 10-1", "(tpr, fpr, ratio)", get_tpr_at_frp(tpr, fpr, 0.1))

            ax.plot(
                fpr,
                tpr,
                lw=2,
                color=label_to_color[label],
                label=f"label {label} (AUC={roc_auc:.2f})",
            )

        ax.plot([0, 1], [0, 1], "k--")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title(f"Client {client_num} {client} {plot_title}")
        ax.legend(loc="lower right")
        plt.savefig(f"{plot_path}_{client}_roc_by_label.png", bbox_inches="tight")

        ax.set_title(f"Client {client_num} {client} {plot_title} (log-log)")
        ax.set_xscale("log")
        ax.set_yscale("log")

        plt.savefig(f"{plot_path}_{client}_roc_by_label_loglog.png")
        plt.close()


def plot_ROCs(
    df_attack,
    df_gt,
    cid_list,
    plot_title,
    plot_path,
    round_num=-1,
    approach="higher_whisker",
):
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
        y_pred, y_pred_bin = get_y_pred(df_attack, client, approach)
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
        plt.xscale("log")
        plt.yscale("log")
        plt.savefig(f"{plot_path}_{client}_loglog.png")
        plt.close()


if __name__ == "__main__":
    args = parse_args()

    approach = args.approach
    save_folder = args.save_folder
    ground_truth_folder = args.ground_truth_folder
    round_path = args.round_path
    dic_client_name = args.dic_client_name
    plot_per_label = args.plot_per_label

    print("approach:", approach)
    print("save_folder:", save_folder)
    print("ground_truth_folder:", ground_truth_folder)
    print("round_path:", round_path)
    print("dic_client_name:", dic_client_name)

    os.makedirs(save_folder, exist_ok=True)

    df_cosine, df_loss, cid_list, img_cos_selected, img_loss_selected = get_dataframes(
        round_path=round_path,
        cosine_file_name="cosine_matrix.csv",
        loss_file_name="loss_per_instances.csv",
        plot_folder=f"{save_folder}/",
    )

    df_gt = get_groundtruth_dataframes(
        data_split_path=ground_truth_folder,
        save_folder=f"{save_folder}/",
        dic_client_name=dic_client_name,
    )

    # plots per label
    if plot_per_label:
        labels_path = f"{ground_truth_folder}/index_to_label.csv"
        if os.path.isfile(labels_path):
            df_labels = pd.read_csv(labels_path)
            plot_ROCs_label(
                df_attack=df_cosine,
                df_gt=df_gt,
                cid_list=cid_list,
                plot_title="ROC Curve cosine",
                plot_path=f"{save_folder}/ROC_cosine_all",
                df_labels=df_labels,
                approach=approach,
            )

            plot_ROCs_label(
                df_attack=df_loss,
                df_gt=df_gt,
                cid_list=cid_list,
                plot_title="ROC Curve loss",
                plot_path=f"{save_folder}/ROC_loss_all",
                df_labels=df_labels,
                approach=approach,
            )
            for round_num in df_cosine["round"].unique():
                plot_ROCs_label(
                    df_attack=df_cosine,
                    df_gt=df_gt,
                    cid_list=cid_list,
                    plot_title="ROC Curve cosine",
                    plot_path=f"{save_folder}/ROC_cosine_round_{round_num}",
                    df_labels=df_labels,
                    round_num=round_num,
                    approach=approach,
                )

                plot_ROCs_label(
                    df_attack=df_loss,
                    df_gt=df_gt,
                    cid_list=cid_list,
                    plot_title="ROC Curve loss",
                    plot_path=f"{save_folder}/ROC_loss_round_{round_num}",
                    df_labels=df_labels,
                    round_num=round_num,
                    approach=approach,
                )
        else:
            print(f"[ERROR] {labels_path} does not exist, cannot plot per label")
    # plots global
    plot_ROCs(
        df_attack=df_cosine,
        df_gt=df_gt,
        cid_list=cid_list,
        plot_title="ROC Curve cosine",
        plot_path=f"{save_folder}/ROC_cosine_all",
        approach=approach,
    )

    plot_ROCs(
        df_attack=df_loss,
        df_gt=df_gt,
        cid_list=cid_list,
        plot_title="ROC Curve loss",
        plot_path=f"{save_folder}/ROC_loss_all",
        approach=approach,
    )
    for round_num in df_cosine["round"].unique():
        plot_ROCs(
            df_attack=df_cosine,
            df_gt=df_gt,
            cid_list=cid_list,
            plot_title="ROC Curve cosine",
            plot_path=f"{save_folder}/ROC_cosine_round_{round_num}",
            round_num=round_num,
            approach=approach,
        )

        plot_ROCs(
            df_attack=df_loss,
            df_gt=df_gt,
            cid_list=cid_list,
            plot_title="ROC Curve loss",
            plot_path=f"{save_folder}/ROC_loss_round_{round_num}",
            round_num=round_num,
            approach=approach,
        )
