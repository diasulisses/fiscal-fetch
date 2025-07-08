# src/core.py
from gmail_service import get_gmail_service
from query_builder import build_query
from profile_manager import load_profile
from file_handler import save_attachment

class FiscalFetchCore:
    def __init__(self, config):
        self.config = config
        self.service, self.user_email = get_gmail_service()

    def run(self):
        if not self.service:
            print("Could not connect to Gmail. Aborting.")
            return

        print("\n--- Starting Fiscal Fetch ---")
        
        profile_data = load_profile(self.config.get('profile'))
        print(f"Loaded profile: '{self.config.get('profile')}'")

        query = build_query(
            profile_data,
            self.config.get('date_range'),
            self.user_email
        )
        print(f"Constructed search query for user: {self.user_email}")
        if self.config.get('dry_run'):
            print(f"\n[Dry Run] Query would be: {query}\n")

        print("Searching for messages...")
        results = self.service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        if not messages:
            print("No messages found matching your criteria.")
            return

        print(f"Found {len(messages)} messages. Processing...")

        if self.config.get('dry_run'):
            print("\n[Dry Run] Would process the following emails:")

        for message_info in messages:
            msg = self.service.users().messages().get(userId='me', id=message_info['id']).execute()
            
            subject = next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'subject'), 'No Subject')
            
            if self.config.get('dry_run'):
                print(f"  - {subject}")
                continue

            print(f"\nProcessing email: '{subject}'")
            
            if 'parts' in msg['payload']:
                for part in msg['payload']['parts']:
                    if part.get('filename') and part.get('body') and part.get('body').get('attachmentId'):
                        attachment = self.service.users().messages().attachments().get(
                            userId='me', messageId=msg['id'], id=part['body']['attachmentId']
                        ).execute()
                        save_attachment(part['filename'], attachment['data'], self.config.get('output_directory'))

        print("\n--- Fiscal Fetch Finished ---")
