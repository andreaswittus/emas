import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils import (
    read_sql_table,
    upsert_df_to_sql_table,
)  # Import helper functions from utils.py

# Load environment variables from a .env file
load_dotenv()

# Optional: set Pandas option to display full content in cells (for debugging)
pd.set_option("display.max_colwidth", None)


def remove_signature_block(text):
    """
    Removes a signature block from the text.

    This function uses a regular expression to detect common signature phrases
    (case-insensitive) and removes everything from the first occurrence of any
    such phrase onward.
    """
    if not text:
        return text

    # Regex pattern for common signature phrases in multiple languages.
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

    # 1. Parse HTML with BeautifulSoup.
    soup = BeautifulSoup(raw_html, "html.parser")

    # 2. Remove unwanted tags.
    for tag in soup(["script", "style", "img", "table"]):
        tag.decompose()

    # 3. Extract visible text using newline as a separator.
    text = soup.get_text(separator="\n")

    # 4. Collapse extra whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    # 5. Remove signature block.
    text = remove_signature_block(text)

    # 6. Normalize the text: convert to lowercase and remove non-ASCII characters.
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


def main():
    # Read the existing email data from the SQLite database.
    df_emails = read_sql_table("emails")

    if df_emails.empty:
        print("No emails found in the database.")
        return

    # Preview the existing data (raw_body)
    print("Existing email data (raw_body):")
    print(df_emails[["graph_id", "subject", "raw_body"]].head())

    # Process raw_body to generate cleaned_body.
    df_emails = add_cleaned_body_to_dataframe(df_emails)

    # Preview the updated DataFrame with cleaned_body.
    print("\nData after preprocessing (with cleaned_body):")
    print(df_emails[["graph_id", "subject", "cleaned_body"]].head())

    # Upsert the updated DataFrame into the SQLite database.
    upsert_df_to_sql_table("emails", df_emails)

    # Optionally, display the final table contents.
    df_final = read_sql_table("emails")
    print("\nFinal contents of the 'emails' table in the database:")
    print(df_final.head())


if __name__ == "__main__":
    main()
