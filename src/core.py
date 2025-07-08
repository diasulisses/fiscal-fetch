# src/core.py
import csv
import os
import sys
import json
from datetime import datetime
from gmail_service import get_gmail_service
from query_builder import build_query
from profile_manager import load_profile
from file_handler import save_attachment

class CsvLogger:
    """
    A logger to write structured, event-based data to a persistent CSV file.
    """
    def __init__(self, filename="audit_log.csv"):
        self.filename = filename
        self.fieldnames = ['Timestamp', 'Event Type', 'Subject', 'Entity', 'Status', 'Details']
        
        file_exists = os.path.isfile(self.filename)
        
        self.file_handle = open(self.filename, 'a', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.file_handle, fieldnames=self.fieldnames)

        if not file_exists:
            self.writer.writeheader()

    def log(self, event_type: str, subject: str = "N/A", entity: str = "N/A", status: str = "N/A", details: str = "N/A"):
        """Appends a new event row to the CSV log file."""
        self.writer.writerow({
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Event Type': event_type,
            'Subject': subject,
            'Entity': entity,
            'Status': status,
            'Details': details
        })
        self.file_handle.flush()

    def close(self):
        """Closes the file handle."""
        self.file_handle.close()

class FiscalFetchCore:
    def __init__(self, config):
        self.config = config
        self.service, self.user_email = get_gmail_service()
        self.logger = CsvLogger()
        self.index_path = "processed_threads.json"

    def _load_processed_index(self):
        """Loads the set of already processed thread IDs from a file."""
        try:
            with open(self.index_path, 'r') as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def _save_processed_index(self, processed_ids):
        """Saves the updated set of processed thread IDs to a file."""
        with open(self.index_path, 'w') as f:
            json.dump(list(processed_ids), f)

    def _show_progress(self, iteration, total, subject=''):
        """Displays a progress bar in the CLI."""
        bar_length = 40
        filled_length = int(bar_length * iteration // total)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        percent = round(100.0 * iteration / total, 1)
        sys.stdout.write(f'\rProgress: |{bar}| {percent}% ({iteration}/{total}) - Processing: {subject[:40]:<40}')
        sys.stdout.flush()

    def run(self):
        if not self.service:
            print("Could not connect to Gmail. Aborting.")
            return

        print("\n--- Starting Fiscal Fetch ---")
        self.logger.log(event_type="Run Start", status="Success", details=f"Profile: {self.config.get('profile')}, Date Range: {self.config.get('date_range')}")
        
        # 1. Load the index of processed threads
        processed_thread_ids = self._load_processed_index()
        self.logger.log(event_type="Index Load", status="Success", details=f"Loaded {len(processed_thread_ids)} previously processed thread IDs.")

        profile_data = load_profile(self.config.get('profile'))
        query = build_query(profile_data, self.config.get('date_range'), self.user_email)
        
        print("Searching for conversation threads...")
        results = self.service.users().threads().list(userId='me', q=query).execute()
        threads = results.get('threads', [])

        if not threads:
            print("No conversation threads found matching your criteria.")
            self.logger.log(event_type="Run End", status="Success", details="No threads found.")
            self.logger.close()
            return
        
        # 2. Filter out threads that have already been processed
        all_found_threads = {t['id'] for t in threads}
        new_threads_to_process = [t for t in threads if t['id'] not in processed_thread_ids]

        total_threads = len(new_threads_to_process)
        if total_threads == 0:
            print(f"Found {len(all_found_threads)} threads, but all have been processed previously.")
            self.logger.log(event_type="Run End", status="Success", details="No new threads to process.")
            self.logger.close()
            return
            
        print(f"Found {len(all_found_threads)} total threads, {total_threads} are new. Processing attachments...")
        
        processed_attachment_ids_this_run = set()

        self._show_progress(0, total_threads)

        for i, thread_info in enumerate(new_threads_to_process):
            thread = self.service.users().threads().get(userId='me', id=thread_info['id']).execute()
            
            for msg in thread['messages']:
                subject = next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'subject'), 'No Subject')
                self._show_progress(i + 1, total_threads, subject)

                if 'parts' in msg['payload']:
                    for part in msg['payload']['parts']:
                        attachment_id = part.get('body', {}).get('attachmentId')
                        filename = part.get('filename')

                        if filename and attachment_id:
                            if attachment_id in processed_attachment_ids_this_run:
                                continue
                            
                            processed_attachment_ids_this_run.add(attachment_id)
                            
                            timestamp_ms = int(msg['internalDate'])
                            email_date = datetime.fromtimestamp(timestamp_ms / 1000)
                            
                            if self.config.get('dry_run'):
                                self.logger.log(event_type="Attachment Process", subject=subject, entity=filename, status="Skipped", details="Dry Run")
                                continue

                            attachment_data = self.service.users().messages().attachments().get(
                                userId='me', messageId=msg['id'], id=attachment_id
                            ).execute()
                            
                            result = save_attachment(
                                filename,
                                attachment_data['data'],
                                self.config.get('output_directory'),
                                email_date
                            )
                            
                            self.logger.log(event_type="Attachment Process", subject=subject, entity=filename, status=result['status'], details=result['details'])
            
            # 3. Add the thread ID to our main index after it's fully processed
            processed_thread_ids.add(thread_info['id'])

        # 4. Save the updated index back to the file
        self._save_processed_index(processed_thread_ids)
        self.logger.log(event_type="Index Save", status="Success", details=f"Saved {len(processed_thread_ids)} total processed thread IDs to index.")

        print("\n\n--- Fiscal Fetch Finished ---")
        print("See audit_log.csv for a detailed report.")
        self.logger.log(event_type="Run End", status="Success", details=f"Processed {total_threads} new threads.")
        self.logger.close()
