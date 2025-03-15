import os
import sqlite3
import requests
import re
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils import read_sql_table, upsert_df_to_sql_table

# resetting the database
from utils import _database_path


def clear_emails_table_drop():
    db_path = _database_path()
    print(f"Database path: {db_path}")
    try:
        with sqlite3.connect(db_path) as con:
            con.execute("DROP TABLE IF EXISTS emails")
            con.commit()
        print("The 'emails' table has been dropped.")
    except Exception as e:
        print("Error while dropping the 'emails' table:", e)


clear_emails_table_drop()

# Load environment variables
load_dotenv()

pd.set_option("display.max_colwidth", None)


def get_access_token():
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    if not tenant_id or not client_id or not client_secret:
        print("Missing environment variables TENANT_ID, CLIENT_ID, or CLIENT_SECRET.")
        return None
    auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }
    try:
        resp = requests.post(auth_url, data=data)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error requesting token: {e}")
        return None
    token_json = resp.json()
    access_token = token_json.get("access_token")
    if not access_token:
        print("No access_token in response. Full response:", token_json)
        return None
    return access_token


def fetch_all_emails_uniquebody(access_token, user_email, folder_name=None):
    """
    Fetches all emails from the given mailbox using Microsoft Graph API.
    Uses the 'uniqueBody' field to retrieve only the new content of each email.

    Parameters:
      - access_token: Bearer token from Azure AD.
      - user_email: The mailbox email address (e.g., "salessupport@dacapo.com").
      - folder_name: (Optional) The specific folder to fetch emails from (e.g., "Archive").

    Returns:
      A list of dictionaries containing email fields.
    """
    base_url = f"https://graph.microsoft.com/v1.0/users/{user_email.lower()}"
    folder_id = None

    if folder_name:
        folder_resp = requests.get(
            base_url + "/mailFolders",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        if folder_resp.status_code == 200:
            folders = folder_resp.json().get("value", [])
            for f in folders:
                if f.get("displayName") == folder_name:
                    folder_id = f["id"]
                    break
        else:
            print("Could not retrieve folder list, status:", folder_resp.status_code)

    if folder_id:
        messages_url = f"{base_url}/mailFolders/{folder_id}/messages"
    else:
        messages_url = f"{base_url}/messages"

    params = {
        "$select": (
            "id,conversationId,subject,from,toRecipients,ccRecipients,bccRecipients,"
            "receivedDateTime,sentDateTime,uniqueBody"
        ),
        "$top": "100",  # You can adjust this page size as needed.
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    all_results = []
    next_link = messages_url

    while next_link:
        try:
            resp = requests.get(
                next_link,
                headers=headers,
                params=params if next_link == messages_url else None,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print("Error fetching messages:", e)
            break

        data = resp.json()
        items = data.get("value", [])
        for item in items:
            email_dict = {}
            email_dict["graph_id"] = item.get("id")
            email_dict["conversation_id"] = item.get("conversationId")
            email_dict["subject"] = item.get("subject")
            email_dict["sender"] = (
                item.get("from", {}).get("emailAddress", {}).get("address", "").lower()
            )
            to_list = [
                r["emailAddress"]["address"].lower()
                for r in item.get("toRecipients", [])
                if r.get("emailAddress")
            ]
            cc_list = [
                r["emailAddress"]["address"].lower()
                for r in item.get("ccRecipients", [])
                if r.get("emailAddress")
            ]
            bcc_list = [
                r["emailAddress"]["address"].lower()
                for r in item.get("bccRecipients", [])
                if r.get("emailAddress")
            ]
            email_dict["to_list"] = ", ".join(to_list)
            email_dict["cc_list"] = ", ".join(cc_list)
            email_dict["bcc_list"] = ", ".join(bcc_list)
            email_dict["received_datetime"] = item.get("receivedDateTime")
            email_dict["sent_datetime"] = item.get("sentDateTime")
            email_dict["raw_body"] = item.get("uniqueBody", {}).get("content", "")
            email_dict["folder_name"] = folder_name if folder_name else "(top-level)"
            all_results.append(email_dict)

        # Check for pagination: the Graph API returns '@odata.nextLink' when more data is available.
        next_link = data.get("@odata.nextLink")
        if next_link:
            print("Fetching next page...")

    return all_results


def fetch_emails_dataframe(token, user_email, folder_name="Archive"):
    """
    Fetches all email data using raw 'uniqueBody' and returns a Pandas DataFrame.
    The DataFrame contains columns:
      graph_id, conversationId, subject, sender, to_list, cc_list, bcc_list,
      received_datetime, sent_datetime, raw_body, folder_name.
    """
    emails_data = fetch_all_emails_uniquebody(token, user_email, folder_name)
    if not emails_data:
        print("No email data fetched.")
        return pd.DataFrame()
    df = pd.DataFrame(
        emails_data,
        columns=[
            "graph_id",
            "conversation_id",
            "subject",
            "sender",
            "to_list",
            "cc_list",
            "bcc_list",
            "received_datetime",
            "sent_datetime",
            "raw_body",
            "folder_name",
        ],
    )
    return df


def main():
    token = get_access_token()
    if not token:
        print("Failed to retrieve access token. Stopping.")
        return

    # Define the mailbox and folder.
    user_email = "salessupport@dacapo.com"
    folder_name = "Archive"

    # Fetch all email data and convert it into a DataFrame.
    df_emails = fetch_emails_dataframe(token, user_email, folder_name)
    if df_emails.empty:
        print("No email data available to insert.")
        return

    print(
        f"Fetched {len(df_emails)} emails from {folder_name or '(top-level)'} folder:"
    )
    print(df_emails.head())

    # Upsert the DataFrame into the SQLite database table named "emails".
    upsert_df_to_sql_table("emails", df_emails)

    # Read back and display the contents of the 'emails' table for verification.
    df_db = read_sql_table("emails")
    print("\nCurrent contents of the 'emails' table in the database:")
    print(df_db.head())


if __name__ == "__main__":
    main()
