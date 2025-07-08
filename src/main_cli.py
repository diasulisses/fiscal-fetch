# src/main_cli.py
import argparse
import sys
import os

# This adds the project's root directory to the Python path
# to ensure that modules in 'src' can be found.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.core import FiscalFetchCore

def main():
    """
    The main entry point for the Fiscal Fetch CLI.
    Parses command-line arguments and triggers the core logic.
    """
    parser = argparse.ArgumentParser(
        description="A tool to fetch financial documents from your Gmail account."
    )

    parser.add_argument(
        "--profile",
        type=str,
        default="default",
        help="The name of the search profile to use (e.g., 'marketing-agency'). Defaults to 'default'."
    )
    parser.add_argument(
        "--date-range",
        type=str,
        required=True,
        help="The date range for the search. Use 'YYYY' for a full year or 'YYYY-MM-DD:YYYY-MM-DD' for a specific range."
    )
    parser.add_argument(
        "--output-directory",
        type=str,
        default="downloads",
        help="The directory where files will be saved. Defaults to 'downloads'."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true", # This makes it a flag, no value needed
        help="Perform a dry run without downloading any files. Lists the emails that would be processed."
    )

    args = parser.parse_args()

    # Convert the parsed arguments into a dictionary to use as configuration
    config = vars(args)

    # Create an instance of our core application and run it
    app = FiscalFetchCore(config)
    app.run()

if __name__ == '__main__':
    main()
