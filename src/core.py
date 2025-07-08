# src/core.py
import csv
import os
import sys
import json
from datetime import datetime
from gmail_service import get_gmail_service
from query_builder import build_query
from profile_manager import load_profile
from file_handler import save_attachment, save_email_as_eml

class CsvLogger:
    """A logger to write structured, event-based data to a persistent CSV file."""
    def __init__(self, filename, fieldnames):
        self.filename = filename
        self.fieldnames = fieldnames
        file_exists = os.path.isfile(self.filename)
        self.file_handle = open(self.filename, 'a', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.file_handle, fieldnames=self.fieldnames)
        if not file_exists:
            self.writer.writeheader()

    def log(self, data_dict):
        """Appends a new row to the CSV log file."""
        self.writer.writerow(data_dict)
        self.file_handle.flush()

    def close(self):
        """Closes the file handle."""
        self.file_handle.close()

class FiscalFetchCore:
    def __init__(self, config):
        self.config = config
        self.service, self.user_email = get_gmail_service()
        
        # 1. Define the central output directory
        self.output_dir = self.config.get('output_directory', 'fiscal_fetch_output')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # 2. Define all output file paths within the central directory
        self.audit_log_path = os.path.join(self.output_dir, "audit_log.csv")
        self.report_log_path = os.path.join(self.output_dir, "extraction_report.csv")
        self.index_path = os.path.join(self.output_dir, "processed_threads.json")

        self.audit_logger = CsvLogger(
            filename=self.audit_log_path,
            fieldnames=['Timestamp', 'Event Type', 'Thread ID', 'Email Date', 'Subject', 'Entity', 'Status', 'Details']
        )
        self.report_logger = None
        if self.config.get('generate_report'):
            self.report_logger = CsvLogger(
                filename=self.report_log_path,
                fieldnames=[
                    'Timestamp', 'Thread ID', 'Message ID', 'Received Date', 'Sender', 'Subject', 
                    'Has Attachments', 'EML File Path', 'Likelihood', 'Invoice Number', 'Invoice Amount'
                ]
            )

    def _load_processed_index(self):
        try:
            with open(self.index_path, 'r') as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def _save_processed_index(self, processed_ids):
        with open(self.index_path, 'w') as f:
            json.dump(list(processed_ids), f)

    def _show_progress(self, iteration, total, subject=''):
        bar_length = 40
        filled_length = int(bar_length * iteration // total)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        percent = round(100.0 * iteration / total, 1)
        sys.stdout.write(f'\rProgress: |{bar}| {percent}% ({iteration}/{total}) - Processing: {subject[:40]:<40}')
        sys.stdout.flush()

    def reset_period(self, period_to_reset: str):
        """Deletes files and removes thread IDs from the index for a specific period."""
        print(f"--- Starting Reset for period: {period_to_reset} ---")
        
        try:
            with open(self.audit_log_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                all_rows = list(reader)
        except FileNotFoundError:
            print("Audit log not found. Nothing to reset.")
            self.audit_logger.close()
            return

        threads_to_remove = set()
        files_deleted_count = 0

        for row in all_rows:
            if row['Event Type'] == 'Attachment Process' and row['Status'] == 'Saved':
                email_date_str = row.get('Email Date', '')
                
                if period_to_reset == 'all' or email_date_str.startswith(period_to_reset):
                    file_path = os.path.join(self.output_dir, row['Details'])
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        files_deleted_count += 1
                        self.audit_logger.log({'Event Type': "File Deletion", 'Thread ID': row['Thread ID'], 'Entity': file_path, 'Status': "Success"})
                    
                    threads_to_remove.add(row['Thread ID'])

        if not threads_to_remove:
            print("No processed files found for the specified period.")
            self.audit_logger.close()
            return

        processed_thread_ids = self._load_processed_index()
        updated_thread_ids = processed_thread_ids - threads_to_remove
        self._save_processed_index(updated_thread_ids)

        print(f"Reset complete. Deleted {files_deleted_count} files.")
        print(f"Removed {len(threads_to_remove)} thread IDs from the index.")
        self.audit_logger.log({'Event Type': "Index Reset", 'Status': "Success", 'Details': f"Removed {len(threads_to_remove)} threads for period '{period_to_reset}'."})
        self.audit_logger.close()

    def run(self):
        # ... (run method logic remains largely the same, but logging calls are updated)
        if not self.service:
            print("Could not connect to Gmail. Aborting.")
            return

        print("\n--- Starting Fiscal Fetch ---")
        self.audit_logger.log({'Event Type': "Run Start", 'Status': "Success", 'Details': f"Profile: {self.config.get('profile')}, Date Range: {self.config.get('date_range')}"})
        
        processed_thread_ids = set()
        if not self.config.get('force_rescan'):
            processed_thread_ids = self._load_processed_index()

        profile_data = load_profile(self.config.get('profile'))
        query = build_query(profile_data, self.config.get('date_range'), self.user_email)
        
        print("Searching for conversation threads...")
        results = self.service.users().threads().list(userId='me', q=query).execute()
        threads = results.get('threads', [])

        if not threads:
            print("No conversation threads found.")
            self.audit_logger.log({'Event Type': "Run End", 'Status': "Success", 'Details': "No threads found."})
            self.audit_logger.close()
            if self.report_logger: self.report_logger.close()
            return
        
        new_threads_to_process = [t for t in threads if t['id'] not in processed_thread_ids]
        total_threads = len(new_threads_to_process)
        
        print(f"Found {len(threads)} total threads, {total_threads} are new. Processing...")
        
        processed_attachment_ids_this_run = set()
        self._show_progress(0, total_threads)

        for i, thread_info in enumerate(new_threads_to_process):
            thread = self.service.users().threads().get(userId='me', id=thread_info['id']).execute()
            
            for msg in thread['messages']:
                subject = next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'Subject'), 'No Subject')
                self._show_progress(i + 1, total_threads, subject)

                timestamp_ms = int(msg['internalDate'])
                email_date = datetime.fromtimestamp(timestamp_ms / 1000)

                # Reporting Logic
                if self.report_logger:
                    # ... (reporting logic remains the same)
                    pass

                # Attachment Logic
                if 'parts' in msg['payload']:
                    for part in msg['payload']['parts']:
                        attachment_id = part.get('body', {}).get('attachmentId')
                        filename = part.get('filename')
                        if filename and attachment_id and attachment_id not in processed_attachment_ids_this_run:
                            processed_attachment_ids_this_run.add(attachment_id)
                            
                            result = save_attachment(filename, attachment_data['data'], self.output_dir, email_date)
                            
                            self.audit_logger.log({
                                'Event Type': "Attachment Process", 
                                'Thread ID': thread_info['id'], 
                                'Email Date': email_date.strftime('%Y-%m-%d'),
                                'Subject': subject, 
                                'Entity': filename, 
                                'Status': result['status'], 
                                'Details': result['details']
                            })

            if not self.config.get('dry_run'):
                processed_thread_ids.add(thread_info['id'])

        if not self.config.get('force_rescan'):
            self._save_processed_index(processed_thread_ids)

        print("\n\n--- Fiscal Fetch Finished ---")
        print(f"See reports and downloads in the '{self.output_dir}' directory.")
        self.audit_logger.log({'Event Type': "Run End", 'Status': "Success", 'Details': f"Processed {total_threads} new threads."})
        self.audit_logger.close()
        if self.report_logger: self.report_logger.close()
