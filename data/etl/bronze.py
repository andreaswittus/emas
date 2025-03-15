import pandas as pd
import os
import requests
import re
import json
from bs4 import BeautifulSoup
from utils import upsert_df_to_sql_table, read_sql_table

# Insert Secrets

def get_access_token():

    # Load environment variables from .env file

    # Fetch credentials from environment variables
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")

    # Validate that required environment variables are set
    if not all([tenant_id, client_id, client_secret]):
        raise ValueError("Missing required environment variables: TENANT_ID, CLIENT_ID, or CLIENT_SECRET.")

    auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://graph.microsoft.com/.default'
    }

    try:
        response = requests.post(auth_url, data=data)
        response.raise_for_status()  # Raises an exception for HTTP errors (4xx, 5xx)
        json_data = response.json()
        access_token = json_data.get('access_token')

        if not access_token:
            raise ValueError(f"Response does not contain an access_token. Full response: {json_data}")

        return access_token

    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Error requesting token: {e}")


def html_to_clean_text(html):
  from bs4 import BeautifulSoup
  BeautifulSoup(html, "html.parser").get_text()
  return

def html_to_clean_text(html):
    """Convert HTML content to clean text."""
    return BeautifulSoup(html, "html.parser").get_text() if html else ""

def fetch_emails_for_training(access_token, user_email, folder_name=None, top=10):
    """
    Fetch all emails from the specified folder in the user's mailbox.

    - If folder_name is provided, it retrieves emails only from that folder.
    - If folder_name is not provided, it retrieves from the default Inbox.

    Returns a list of dictionaries with cleaned fields for training.
    """
    if not access_token:
        print("No access token provided.")
        return []
    if not user_email:
        print("No user_email provided.")
        return []

    base_url = f"https://graph.microsoft.com/v1.0/users/{user_email}"
    
    # 1) Find Folder ID if a folder name is provided
    folder_id = None
    if folder_name:
        folder_url = f"{base_url}/mailFolders"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        try:
            folder_resp = requests.get(folder_url, headers=headers)
            folder_resp.raise_for_status()
            folders_data = folder_resp.json().get("value", [])
            for f in folders_data:
                if f.get("displayName") == folder_name:
                    folder_id = f["id"]
                    break
        except requests.exceptions.RequestException as e:
            print("Error looking for folder:", e)
            return None

    # 2) Define the API endpoint
    if folder_id:
        mail_endpoint = f"{base_url}/mailFolders/{folder_id}/messages"
    else:
        mail_endpoint = f"{base_url}/mailFolders/Inbox/messages"  # Default to Inbox if no folder specified

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    params = {
        '$select': 'id,subject,from,toRecipients,ccRecipients,bccRecipients,body,receivedDateTime,sentDateTime,conversationId,uniqueBody',
        '$top': '100'  # Fetch in batches of 100 for efficiency
    }

    all_emails = []
    next_link = mail_endpoint  # Start with the main request URL

    while next_link:
        try:
            response = requests.get(next_link, headers=headers, params=params if next_link == mail_endpoint else None)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error calling Microsoft Graph: {e}")
            return None  # Return None on failure

        print("HTTP Status Code:", response.status_code)

        if response.status_code == 200:
            data = response.json()
            emails = data.get("value", [])

            if not emails:
                print(f"No emails found in the {folder_name if folder_name else 'Inbox'} folder.")
                break

            for email in emails:
                email_data = {
                    "id": email.get("id"),
                    "subject": email.get("subject"),
                    "sender": email.get("from", {}).get("emailAddress", {}).get("address"),
                    "receivedDateTime": email.get("receivedDateTime"),
                    "sentDateTime": email.get("sentDateTime"),
                    "conversationId": email.get("conversationId"),
                    "toRecipients": [rec.get("emailAddress", {}).get("address") for rec in email.get("toRecipients", [])],
                    "ccRecipients": [rec.get("emailAddress", {}).get("address") for rec in email.get("ccRecipients", [])],
                    "bccRecipients": [rec.get("emailAddress", {}).get("address") for rec in email.get("bccRecipients", [])],
                    "uniqueBody": html_to_clean_text(email.get("uniqueBody", {}).get("content", "")),
                    "Body": html_to_clean_text(email.get("body", {}).get("content", ""))
                }
                all_emails.append(email_data)

            # **Fix Pagination Handling**
            next_link = data.get("@odata.nextLink")  # Follow the next page if exists

        else:
            print(f"Error: {response.status_code}, {response.text}")
            return None

    return all_emails  # Return all emails from the specified folder

def run_email_data_pipeline():
    # 1) Get token
    token = get_access_token()
    if not token:
        print("No token, stopping.")
        return None  # Return None to indicate failure

    # 2) Choose mailbox & folder
    user_email = "salessupport@dacapo.com"  # or your mailbox
    folder_name = "Archive"  # or None if top-level

    # 3) Fetch emails
    emails_data = fetch_emails_for_training(token, user_email, folder_name=folder_name)
    print(f"Fetched {len(emails_data)} emails from {folder_name or 'top-level'}.")

    # 4) Convert emails to a Pandas DataFrame
    if not emails_data:
        print("No emails fetched. Exiting pipeline.")
        return None  # Return None if no emails are fetched

    email_df = pd.DataFrame(emails_data)

    return email_df

email_df = run_email_data_pipeline()

def clean_dataframe_for_sql(df):
    """
    Converts list-type columns to string before inserting into SQL.
    """
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, list)).any():  # Check if column contains lists
            df[col] = df[col].apply(lambda x: ",".join(x) if isinstance(x, list) else x)  # Convert lists to comma-separated strings
    return df

email_df = clean_dataframe_for_sql(email_df)

upsert_df_to_sql_table("training_emails", email_df)