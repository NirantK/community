from datetime import timedelta
from pathlib import Path

import fire
import pandas as pd
from loguru import logger
from parsing_utils import WhatsAppMessageExtractor
from rich import print


def get_top_senders(df, freq: str, k: int = 5) -> pd.DataFrame:
    """
    Get the top K senders per week.

    Args:
        df (_type_): _description_
        freq (str): _description_
        k (int, optional): _description_. Defaults to 5.

    Returns:
        pd.DataFrame: _description_
    """
    if freq not in ["W", "M"]:
        raise ValueError("freq must be 'W' or 'M'")
    # If 'Datetime' is not the index, set it as the index
    logger.info(f"Index name: {df.index.name}, type: {type(df.index)}")
    if df.index.name != "Datetime":
        df["Datetime"] = pd.to_datetime(df["Datetime"])
        df.set_index("Datetime", inplace=True)  # Set 'Datetime' as index
        df.sort_index(inplace=True)  # Sort the DataFrame based on the index
        logger.info(f"Index name: {df.index.name}, type: {type(df.index)}")
    resampled = df.groupby("Sender").resample(freq).count()
    resampled.reset_index("Datetime", inplace=True)  # Reset only the 'Datetime' index
    sorted_grouped = (
        resampled["Message"]
        .reset_index()
        .sort_values(["Datetime", "Message"], ascending=[True, False])
        .groupby("Datetime")
    )
    top_senders = sorted_grouped.head(k)
    return top_senders


class ActivityStats:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df
        if self.df.index.name != "Datetime":
            self.df.set_index("Datetime", inplace=True)
            self.df.sort_index(inplace=True)

    def compute_sender_stats(self) -> None:
        # Resample DataFrame to a weekly frequency
        weekly_data = self.df.resample("W").count()

        # Initialize lists to store the counts
        new_senders, active_senders, churned_senders = [], [], []

        # Initialize sets for active and churned senders
        current_senders, previous_senders, churned = set(), set(), set()

        # Time window to consider a sender as churned (21 days)
        churn_window = timedelta(days=21)

        # Iterate through each week
        for week in weekly_data.index:
            # Get the data for the current week
            current_week_data = self.df.truncate(
                before=week - timedelta(weeks=1) + timedelta(seconds=1), after=week
            )

            # Calculate new, active, and churned senders for the current week
            new_senders_count, active_senders_count, churned_senders_count = 0, 0, 0

            for sender in current_week_data["Sender"].unique():
                # Check if the sender is new
                if sender not in current_senders and sender not in previous_senders:
                    new_senders_count += 1
                    current_senders.add(sender)

                # Check if the sender is active
                if sender in current_senders or sender in previous_senders:
                    active_senders_count += 1
                    current_senders.add(sender)

            # Update churned senders
            for sender in previous_senders:
                if (
                    sender not in current_senders
                    and (week - self.df[self.df["Sender"] == sender].index[-1])
                    > churn_window
                ):
                    churned_senders_count += 1
                    churned.add(sender)

            # Store the results in the lists
            new_senders.append(new_senders_count)
            active_senders.append(active_senders_count)
            churned_senders.append(churned_senders_count)

            # Update previous_senders for the next iteration
            previous_senders.update(current_senders)
            current_senders.clear()

        result_df = pd.DataFrame(
            {
                "Date": weekly_data.index,
                "New Senders": new_senders,
                "Active Senders": active_senders,
                "Churned Senders": churned_senders,
            }
        )
        result_df.set_index("Date", inplace=True)
        return result_df


def compute(readpath: str, k: int) -> None:
    """
    Compute the stats.

    Args:
        readpath (str): Path to the WhatsApp chat file.
        k (int): Number of top senders to consider.
    """
    readpath = Path(readpath)
    assert readpath.exists()
    msg_extractor = WhatsAppMessageExtractor(file_path=readpath)
    messages = msg_extractor.extract_messages()
    df = pd.DataFrame(messages, columns=["Sender", "Datetime", "Message"])

    # Top K senders per week
    weekly_top_senders = get_top_senders(df, freq="W", k=k)
    print(f"Top {k} senders per week:\n{weekly_top_senders}")

    monthly_top_senders = get_top_senders(df, freq="M", k=k)
    print(f"Top {k} senders per month:\n{monthly_top_senders}")

    weekly_senders = ActivityStats(df)
    stats_df = weekly_senders.compute_sender_stats()
    print("Weekly sender stats:")
    print(stats_df)


if __name__ == "__main__":
    fire.Fire(compute)
