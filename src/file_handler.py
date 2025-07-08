# src/file_handler.py
import os
import base64

def save_attachment(filename: str, data: str, output_dir: str):
    """
    Decodes base64 data and saves it as a file.

    Args:
        filename: The name of the file to save.
        data: The base64-encoded file data.
        output_dir: The directory to save the file in.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Sanitize filename (basic version)
    safe_filename = "".join(c for c in filename if c.isalnum() or c in ('.', '_', '-')).strip()
    if not safe_filename:
        safe_filename = "unnamed_attachment"

    file_path = os.path.join(output_dir, safe_filename)
    
    try:
        decoded_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        print(f"  + Saved attachment: {safe_filename}")
    except Exception as e:
        print(f"  - Error saving attachment {safe_filename}: {e}")

# --- PDF Functionality (Temporarily Disabled) ---
# def save_email_as_pdf(subject, body_html, output_dir):
#     from bs4 import BeautifulSoup
#     import weasyprint
#     # ... implementation would go here ...
#     print("Saving email as PDF is currently disabled.")
