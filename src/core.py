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
        # Create directory for the file if it doesn't exist
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        file_exists = os.path.isfile(self.filename)
        self.file_handle = open(self.filename, 'a', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.file_handle, fieldnames=self.fieldnames)
        if not file_exists:
            self.writer.writeheader()

    def log(self, data_dict):
        """Appends a new row to the CSV log file."""
        filtered_data = {k: v for k, v in data_dict.items() if k in self.fieldnames}
        self.writer.writerow(filtered_data)
        self.file_handle.flush()

    def close(self):
        """Closes the file handle."""
        self.file_handle.close()

class FiscalFetchCore:
    def __init__(self, config):
        self.config = config
        self.service, self.user_email = get_gmail_service()
        
        self.output_dir = self.config.get('output_directory', 'fiscal_fetch_output')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # All logs and indexes are now inside the main output directory
        self.audit_log_path = os.path.join(self.output_dir, "logs", "audit_log.csv")
        self.index_path = os.path.join(self.output_dir, ".state", "processed_threads.json")

        self.audit_logger = CsvLogger(
            filename=self.audit_log_path,
            fieldnames=['Timestamp', 'Event Type', 'Thread ID', 'Email Date', 'Subject', 'Entity', 'Status', 'Details']
        )
        self.report_logger = None
        # *** FIX IS HERE ***
        # Only set up the report logger if a date_range is provided (i.e., it's a 'run' command)
        if self.config.get('date_range') and not self.config.get('no_report'):
            run_timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            date_range_str = self.config.get('date_range').replace(':', '_to_')
            report_filename = f"{run_timestamp}_report_for_{date_range_str}.csv"
            report_path = os.path.join(self.output_dir, "reports", report_filename)

            self.report_logger = CsvLogger(
                filename=report_path,
                fieldnames=[
                    'Timestamp', 'Thread ID', 'Message ID', 'Received Date', 'Sender', 'To', 'Cc', 
                    'Subject', 'Attachment Count', 'EML File Path', 'Likelihood', 'Invoice Number', 'Invoice Amount'
                ]
            )

    def _load_processed_index(self):
        """Loads the set of already processed thread IDs from a file."""
        try:
            with open(self.index_path, 'r') as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def _save_processed_index(self, processed_ids):
        """Saves the updated set of processed thread IDs to a file."""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        with open(self.index_path, 'w') as f:
            json.dump(list(processed_ids), f)

    def _show_progress(self, iteration, total, status_message=''):
        """Displays a progress bar with a generic status message."""
        bar_length = 40
        filled_length = int(bar_length * iteration // total)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        percent = round(100.0 * iteration / total, 1)
        sys.stdout.write(f'\rProgress: |{bar}| {percent}% ({iteration}/{total}) - {status_message:<50}')
        sys.stdout.flush()

    def reset_period(self, period_to_reset: str):
        """Deletes files and reports, and removes thread IDs from the index for a specific period."""
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
                
                if period_to_reset == 'all' or (email_date_str and email_date_str.startswith(period_to_reset)):
                    file_path = os.path.join(self.output_dir, row['Details'])
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            files_deleted_count += 1
                            self.audit_logger.log({'Event Type': "File Deletion", 'Thread ID': row['Thread ID'], 'Entity': file_path, 'Status': "Success"})
                        except OSError as e:
                            self.audit_logger.log({'Event Type': "File Deletion", 'Thread ID': row['Thread ID'], 'Entity': file_path, 'Status': "Error", 'Details': str(e)})
                    
                    threads_to_remove.add(row['Thread ID'])

        reports_dir = os.path.join(self.output_dir, "reports")
        reports_deleted_count = 0
        if os.path.exists(reports_dir):
            for report_filename in os.listdir(reports_dir):
                if period_to_reset == 'all' or period_to_reset in report_filename:
                    report_path = os.path.join(reports_dir, report_filename)
                    try:
                        os.remove(report_path)
                        reports_deleted_count += 1
                        self.audit_logger.log({'Event Type': "Report Deletion", 'Entity': report_path, 'Status': "Success"})
                    except OSError as e:
                        self.audit_logger.log({'Event Type': "Report Deletion", 'Entity': report_path, 'Status': "Error", 'Details': str(e)})

        if not threads_to_remove and reports_deleted_count == 0:
            print("No processed files or reports found for the specified period.")
            self.audit_logger.close()
            return

        processed_thread_ids = self._load_processed_index()
        updated_thread_ids = processed_thread_ids - threads_to_remove
        self._save_processed_index(updated_thread_ids)

        print(f"Reset complete. Deleted {files_deleted_count} downloaded files and {reports_deleted_count} reports.")
        print(f"Removed {len(threads_to_remove)} thread IDs from the index.")
        self.audit_logger.log({'Event Type': "Index Reset", 'Status': "Success", 'Details': f"Removed {len(threads_to_remove)} threads for period '{period_to_reset}'."})
        self.audit_logger.close()

    def run(self):
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
        self._show_progress(0, total_threads, "Initializing...")

        for i, thread_info in enumerate(new_threads_to_process):
            thread = self.service.users().threads().get(userId='me', id=thread_info['id'], format='full').execute()
            
            for msg in thread['messages']:
                subject = next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'subject'), 'No Subject')
                self._show_progress(i + 1, total_threads, subject)

                timestamp_ms = int(msg['internalDate'])
                email_date = datetime.fromtimestamp(timestamp_ms / 1000)

                attachment_count = 0
                if 'parts' in msg['payload']:
                    attachment_count = sum(1 for part in msg['payload']['parts'] if part.get('filename'))

                if self.report_logger:
                    raw_msg = self.service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
                    raw_data = raw_msg['raw']
                    sender = next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'from'), 'No Sender')
                    to_recipients = next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'to'), '')
                    cc_recipients = next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'cc'), '')
                    
                    eml_save_result = save_email_as_eml(msg['id'], raw_data, self.output_dir, email_date)
                    
                    self.report_logger.log({
                        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'Thread ID': msg['threadId'],
                        'Message ID': msg['id'],
                        'Received Date': email_date.strftime('%Y-%m-%d'),
                        'Sender': sender,
                        'To': to_recipients,
                        'Cc': cc_recipients,
                        'Subject': subject,
                        'Attachment Count': attachment_count,
                        'EML File Path': eml_save_result['details'] if eml_save_result['status'] == 'Saved' else 'N/A'
                    })

                if 'parts' in msg['payload']:
                    for part in msg['payload']['parts']:
                        attachment_id = part.get('body', {}).get('attachmentId')
                        filename = part.get('filename')
                        if filename and attachment_id and attachment_id not in processed_attachment_ids_this_run:
                            processed_attachment_ids_this_run.add(attachment_id)
                            
                            if self.config.get('dry_run'):
                                self.audit_logger.log({'Event Type': "Attachment Process", 'Thread ID': thread_info['id'], 'Email Date': email_date.strftime('%Y-%m-%d'), 'Subject': subject, 'Entity': filename, 'Status': "Skipped", 'Details': "Dry Run"})
                                continue

                            attachment_data = self.service.users().messages().attachments().get(
                                userId='me', messageId=msg['id'], id=attachment_id
                            ).execute()

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
