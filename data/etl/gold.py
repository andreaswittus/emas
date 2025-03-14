import sqlite3
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils import (
    read_sql_table,
    upsert_df_to_sql_table,
    _database_path,
)  # Ensure _database_path is available

# Load environment variables from a .env file
load_dotenv()

# Optional: Set Pandas option to display full text in cells for debugging.
pd.set_option("display.max_colwidth", None)


# --- Step 1: Load the mapping Excel file ---
def load_email_department_mapping(mapping_filepath):
    """
    Reads the Excel file containing email-to-department mappings.
    Assumes the Excel file has at least two columns: "email" and "department".
    Returns a dictionary with email addresses as keys and departments as values.
    """
    mapping_df = pd.read_excel(mapping_filepath)
    # Normalize the email addresses to lowercase and strip spaces.
    mapping_df["email"] = mapping_df["email"].str.lower().str.strip()
    mapping_dict = mapping_df.set_index("email")["department"].to_dict()
    return mapping_dict


# --- Step 2: Define Functions for Labeling ---


def assign_sender_department(sender, mapping):
    """
    Returns the department for the sender email based on the mapping.
    """
    if not sender:
        return None
    sender = sender.lower().strip()
    return mapping.get(sender, None)


def assign_departments_from_list(email_list_str, mapping):
    """
    For a comma-separated string of email addresses, returns a comma-separated
    string of unique departments in the order they appear.
    If an email is not found in the mapping, it is replaced with "NULL".

    For example:
      Input: "unknown@dacapo.com, jmn@dacapo.com, jmn@dacapo.com"
      Mapping: unknown -> "NULL", jmn -> "sales"
      Output: "NULL, sales"
    """
    if not email_list_str:
        return None
    # Split and normalize email addresses.
    emails = [e.strip().lower() for e in email_list_str.split(",") if e.strip()]
    unique_depts = []
    seen = set()
    for email in emails:
        dept = mapping.get(email, "NULL")
        if dept not in seen:
            seen.add(dept)
            unique_depts.append(dept)
    return ", ".join(unique_depts)


def add_department_labels(df, mapping):
    """
    Adds 'sender_department', 'to_departments', and 'cc_departments' columns to the DataFrame.
    """
    if "sender" in df.columns:
        df["sender_department"] = df["sender"].apply(
            lambda x: assign_sender_department(x, mapping)
        )
    if "to_list" in df.columns:
        df["to_departments"] = df["to_list"].apply(
            lambda x: assign_departments_from_list(x, mapping)
        )
    if "cc_list" in df.columns:
        df["cc_departments"] = df["cc_list"].apply(
            lambda x: assign_departments_from_list(x, mapping)
        )
    return df


# --- Step 3: Replace the Emails Table with Curated Data ---
def replace_emails_table(df: pd.DataFrame):
    """
    Overwrites the 'emails' table in the SQLite database with the given DataFrame.
    Ensures that only the rows in the DataFrame are stored (e.g. exactly 100 rows).
    """
    db_path = _database_path()
    with sqlite3.connect(db_path) as con:
        df.to_sql("emails", con, if_exists="replace", index=False)
    print(f"Replaced the 'emails' table with {len(df)} rows.")


def filter_and_limit_emails(df):
    """
    Filters the DataFrame to remove rows with duplicate graph_id values and limits to 100 rows.
    """
    df_filtered = df.drop_duplicates(subset=["graph_id"])
    return df_filtered.head(100)


# --- Main Function for Gold Layer Enrichment ---
def main():
    # Step 1: Load existing email data from the SQLite database.
    df_emails = read_sql_table("emails")
    if df_emails.empty:
        print("No emails found in the database.")
        return

    print("Existing email data preview:")
    print(df_emails[["graph_id", "subject", "sender", "to_list", "cc_list"]].head())

    # Step 2: Load the email-to-department mapping from the Excel file.
    mapping_filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Extracted_Employee_Emails_and_Roles.xlsx",
    )
    email_to_dept = load_email_department_mapping(mapping_filepath)
    print("\nEmail-to-department mapping:")
    print(email_to_dept)

    # Step 3: Add department labels to the emails DataFrame.
    df_emails = add_department_labels(df_emails, email_to_dept)

    # Preview the enriched data.
    print("\nData after adding department labels:")
    print(
        df_emails[
            [
                "graph_id",
                "subject",
                "sender_department",
                "to_departments",
                "cc_departments",
            ]
        ].head()
    )

    # Filter and limit to 100 emails.
    df_curated = filter_and_limit_emails(df_emails)
    print(f"\nCurated data (limited to {len(df_curated)} rows):")
    print(
        df_curated[
            [
                "graph_id",
                "subject",
                "sender_department",
                "to_departments",
                "cc_departments",
            ]
        ].head()
    )

    # Replace the 'emails' table with these curated rows.
    replace_emails_table(df_curated)

    # Display the final table for verification.
    df_final = read_sql_table("emails")
    print("\nFinal contents of the 'emails' table:")
    print(df_final.head())


if __name__ == "__main__":
    main()
