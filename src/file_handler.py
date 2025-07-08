# src/file_handler.py
import os
import base64
from datetime import datetime

ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.csv', '.zip', '.eml']

def save_attachment(filename: str, data: str, output_dir: str, email_date: datetime) -> dict:
    """
    Decodes and saves an attachment into a structured directory.
    """
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return {'status': 'Skipped', 'details': f'Disallowed type: {file_ext}'}

    # Create a dedicated "attachments" subfolder
    structured_dir = os.path.join(output_dir, "downloads", str(email_date.year), f"{email_date.month:02d}", "attachments")
    if not os.path.exists(structured_dir):
        os.makedirs(structured_dir)

    safe_filename = "".join(c for c in filename if c.isalnum() or c in ('.', '_', '-')).strip()
    if not safe_filename:
        safe_filename = f"unnamed_attachment{file_ext}"
    
    date_prefix = email_date.strftime('%Y-%m-%d')
    unique_filename = f"{date_prefix}_{safe_filename}"
    
    file_path = os.path.join(structured_dir, unique_filename)

    if os.path.exists(file_path):
        return {'status': 'Skipped', 'details': 'File already exists'}

    try:
        decoded_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        relative_path = os.path.relpath(file_path, output_dir)
        return {'status': 'Saved', 'details': relative_path}
    except Exception as e:
        return {'status': 'Error', 'details': str(e)}

def save_email_as_eml(message_id: str, data: str, output_dir: str, email_date: datetime) -> dict:
    """
    Saves the raw email content as a .eml file.
    """
    # Create a dedicated "emails" subfolder
    structured_dir = os.path.join(output_dir, "downloads", str(email_date.year), f"{email_date.month:02d}", "emails")
    if not os.path.exists(structured_dir):
        os.makedirs(structured_dir)

    date_prefix = email_date.strftime('%Y-%m-%d')
    unique_filename = f"{date_prefix}_{message_id}.eml"
    file_path = os.path.join(structured_dir, unique_filename)

    if os.path.exists(file_path):
        return {'status': 'Skipped', 'details': 'File already exists'}

    try:
        decoded_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        relative_path = os.path.relpath(file_path, output_dir)
        return {'status': 'Saved', 'details': relative_path}
    except Exception as e:
        return {'status': 'Error', 'details': str(e)}
