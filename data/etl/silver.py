import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils import (
    read_sql_table,
    upsert_df_to_sql_table,
)  # Using our common DB helper functions

# This function is used to remove the emails table from the database.
# It is useful when you want to start fresh and remove all existing data.
# import sqlite3
# from utils import _database_path


# def clear_emails_table_drop():
#    db_path = _database_path()
#    print(f"Database path: {db_path}")
#    try:
#        with sqlite3.connect(db_path) as con:
#            con.execute("DROP TABLE IF EXISTS emails")
#            con.commit()
#        print("The 'emails' table has been dropped.")
#    except Exception as e:
#        print("Error while dropping the 'emails' table:", e)

# clear_emails_table_drop()


# Load environment variables from .env file
load_dotenv()

# Optional: Set Pandas option to display full text in cells for debugging.
pd.set_option("display.max_colwidth", None)


def remove_signature_block(text):
    """
    Removes a signature block from the text by searching for common signature phrases.
    Uses a regular expression (case-insensitive) to detect phrases like "best regards",
    "med venlig hilsen", etc. and truncates the text from the first occurrence onward.
    """
    if not text:
        return text

    # Regex pattern for common signature phrases in various languages.
    pattern = re.compile(
        r"(?i)\b(?:best regards|kind regards|sincerely|yours truly|yours faithfully|"
        r"med venlig hilsen|vennlig hilsen|met venlig hilsen|met vriendelijke groet|vriendelijke groet|groeten,)\b"
    )
    match = pattern.search(text)
    if match:
        text = text[: match.start()].strip()
    return text


def clean_email_body(raw_html):
    """
    Cleans the raw HTML email body and returns normalized plain text.

    Steps:
      1. Parse the HTML using BeautifulSoup.
      2. Remove unwanted tags: script, style, img, and table.
      3. Extract visible text.
      4. Collapse extra whitespace.
      5. Remove the signature block using remove_signature_block().
      6. Normalize the text:
           - Convert to lowercase.
           - Remove non-ASCII characters.

    Parameters:
      raw_html (str): Raw HTML content from the email's uniqueBody.

    Returns:
      str: Cleaned and normalized text.
    """
    if not raw_html:
        return ""

    # Parse the HTML.
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove unwanted tags.
    for tag in soup(["script", "style", "img", "table"]):
        tag.decompose()

    # Extract visible text using newline as separator.
    text = soup.get_text(separator="\n")

    # Collapse extra whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    # Remove signature block.
    text = remove_signature_block(text)

    # Normalize: convert to lowercase and remove non-ASCII characters.
    text = text.lower()
    text = text.encode("ascii", errors="ignore").decode("ascii")

    return text


def add_cleaned_body_to_dataframe(df):
    """
    Takes a DataFrame with a 'raw_body' column and adds a new column 'cleaned_body'
    by applying the clean_email_body function to each raw HTML email body.
    """
    if "raw_body" not in df.columns:
        print("The DataFrame does not contain a 'raw_body' column.")
        return df
    df["cleaned_body"] = df["raw_body"].apply(clean_email_body)
    return df


def filter_and_limit_emails(df):
    """
    Filters the DataFrame to remove rows with null/empty cleaned_body values,
    drops duplicates based on graph_id, and limits the DataFrame to 100 rows.
    """
    # Remove rows where cleaned_body is null or empty
    df_filtered = df[
        df["cleaned_body"].notnull() & (df["cleaned_body"].str.strip() != "")
    ]
    # Drop duplicates based on graph_id
    df_filtered = df_filtered.drop_duplicates(subset=["graph_id"])
    # Limit to first 100 rows
    return df_filtered.head(100)


def main():
    # Read existing email data from the SQLite database.
    df_emails = read_sql_table("emails")
    if df_emails.empty:
        print("No emails found in the database.")
        return

    print("Existing email data (raw_body):")
    print(df_emails[["graph_id", "subject", "raw_body"]].head())

    # Add a new column 'cleaned_body' by cleaning raw_body.
    df_emails = add_cleaned_body_to_dataframe(df_emails)

    print("\nData after preprocessing (with cleaned_body):")
    print(df_emails[["graph_id", "subject", "cleaned_body"]].head())

    # Filter and limit to 100 emails.
    df_curated = filter_and_limit_emails(df_emails)
    print(f"\nCurated data (limited to {len(df_curated)} rows):")
    print(df_curated[["graph_id", "subject", "cleaned_body"]].head())

    # Overwrite (replace) the 'emails' table with the curated data.
    upsert_df_to_sql_table("emails", df_curated)

    # Read back and display final contents for verification.
    df_final = read_sql_table("emails")
    print("\nFinal contents of the 'emails' table in the database:")
    print(df_final.head())


if __name__ == "__main__":
    main()
