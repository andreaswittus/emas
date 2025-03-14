import pandas as pd
from dotenv import load_dotenv
from utils import read_sql_table, upsert_df_to_sql_table

# Load environment variables (if using a .env file)
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


def assign_to_departments(to_list_str, mapping):
    """
    For a comma-separated string of recipient emails, returns a comma-separated
    string of unique departments.
    """
    if not to_list_str:
        return None
    # Split and normalize email addresses.
    emails = [e.strip().lower() for e in to_list_str.split(",") if e.strip()]
    departments = set()
    for email in emails:
        dept = mapping.get(email)
        if dept:
            departments.add(dept)
    if departments:
        return ", ".join(sorted(departments))
    return None


def add_department_labels(df, mapping):
    """
    Adds 'sender_department' and 'to_departments' columns to the DataFrame.
    """
    if "sender" in df.columns:
        df["sender_department"] = df["sender"].apply(
            lambda x: assign_sender_department(x, mapping)
        )
    if "to_list" in df.columns:
        df["to_departments"] = df["to_list"].apply(
            lambda x: assign_to_departments(x, mapping)
        )
    return df


# --- Main Function for the Gold Layer Enrichment ---
def main():
    # Step 1: Load existing email data from the SQLite database.
    df_emails = read_sql_table("emails")
    if df_emails.empty:
        print("No emails found in the database.")
        return

    print("Existing email data preview:")
    print(df_emails[["graph_id", "subject", "sender", "to_list"]].head())

    # Step 2: Load the email-to-department mapping from the Excel file.
    mapping_filepath = (
        "Extracted_Employee_Emails_and_Roles.xlsx"  # Adjust the path as needed
    )
    email_to_dept = load_email_department_mapping(mapping_filepath)
    print("\nEmail-to-department mapping:")
    print(email_to_dept)

    # Step 3: Add department labels to the emails DataFrame.
    df_emails = add_department_labels(df_emails, email_to_dept)

    # Preview the enriched data.
    print("\nData after adding department labels:")
    print(
        df_emails[["graph_id", "subject", "sender_department", "to_departments"]].head()
    )

    # (Optional) Further aggregation steps can be applied here before writing to gold layer.
    # For now, we update the silver layer table with these new columns.
    upsert_df_to_sql_table("emails", df_emails)

    # Display the final table for verification.
    df_final = read_sql_table("emails")
    print("\nFinal contents of the 'emails' table:")
    print(df_final.head())


if __name__ == "__main__":
    main()

mapping_df = pd.read_excel("Extracted_Employee_Emails_and_Roles.xlsx")
print("Columns:", mapping_df.columns.tolist())
