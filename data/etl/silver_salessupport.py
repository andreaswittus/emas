import re
import pandas as pd
import sqlite3
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils import (
    read_sql_table,
    upsert_df_to_sql_table,
)  # Using our common DB helper functions

# This function is used to remove the emails table from the database.
# It is useful when you want to start fresh and remove all existing data.
# import sqlite3
from utils import _database_path


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

# Optional: Set Pandas option to display full content in cells (for debugging)
pd.set_option("display.max_colwidth", None)


def remove_signature_block(text):
    """
    Removes a signature block from the text by searching for common signature phrases.
    Uses a regex pattern (case-insensitive) to detect phrases like "best regards", "med venlig hilsen", etc.
    If a match is found, truncates the text from that point onward.
    """
    if not text:
        return text

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
    """
    if not raw_html:
        return ""

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove unwanted tags.
    for tag in soup(["script", "style", "img", "table"]):
        tag.decompose()

    # Extract visible text with newline as a separator.
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
    drops duplicates based on 'graph_id', and limits the DataFrame to 100 rows.
    """
    df_filtered = df[
        df["cleaned_body"].notnull() & (df["cleaned_body"].str.strip() != "")
    ]
    df_filtered = df_filtered.drop_duplicates(subset=["graph_id"])
    return df_filtered.head(100)


def replace_emails_table(table_name: str, df: pd.DataFrame):
    """
    Overwrites the specified table in the SQLite database with the provided DataFrame.
    This function replaces the entire table with the new data.
    """
    db_path = _database_path()
    with sqlite3.connect(db_path) as con:
        df.to_sql(table_name, con, if_exists="replace", index=False)
    print(f"Replaced table '{table_name}' with {len(df)} rows.")


def main():
    # Read existing email data from the SQLite database.
    df_emails = read_sql_table("emails")
    if df_emails.empty:
        print("No emails found in the database.")
        return

    print("Existing email data (raw_body):")
    print(df_emails[["graph_id", "subject", "raw_body"]].head())

    # Process raw_body to generate cleaned_body.
    df_emails = add_cleaned_body_to_dataframe(df_emails)

    print("\nData after preprocessing (with cleaned_body):")
    print(df_emails[["graph_id", "subject", "cleaned_body"]].head())

    # Filter and limit to 100 emails.
    df_curated = filter_and_limit_emails(df_emails)
    print(f"\nCurated data (limited to {len(df_curated)} rows):")
    print(df_curated[["graph_id", "subject", "cleaned_body"]].head())

    # Overwrite (replace) the 'emails' table with the curated data.
    replace_emails_table("emails", df_curated)

    # Read back and display final contents for verification.
    df_final = read_sql_table("emails")
    print("\nFinal contents of the 'emails' table in the database:")
    print(df_final.head())


if __name__ == "__main__":
    main()


# Next steps is to implement the excel file to map the department labels to the emails. ########################################################
# this is done in the gold.py file -- Maybe we should consider inserting it in the silver_salessupport.py file.
