# src/gmail_service.py
import os.path
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """
    Authenticates with the Gmail API and returns a service object and user email.
    """
    creds = None
    if os.path.exists('token.json'):
        try:
            with open('token.json', 'rb') as token:
                creds = pickle.load(token)
        except (pickle.UnpicklingError, EOFError):
            print("Warning: token.json found but is invalid. A new one will be created.")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("ERROR: credentials.json not found in the root directory.")
                return None, None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        email_address = profile['emailAddress']
        return service, email_address
    except Exception as e:
        print(f"An error occurred while building the service: {e}")
        return None, None

if __name__ == '__main__':
    print("Attempting to connect to Gmail API...")
    service, email = get_gmail_service()
    if service:
        print("\nSUCCESS: Successfully connected to the Gmail API.")
        print(f"Authenticated as: {email}")
    else:
        print("\nFAILURE: Could not connect to the Gmail API.")
