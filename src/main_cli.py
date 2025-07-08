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
        description="A tool to fetch and manage financial documents from your Gmail account."
    )

    # Main "run" arguments
    parser.add_argument(
        "--profile",
        type=str,
        default="default",
        help="The name of the search profile to use (e.g., 'marketing-agency')."
    )
    parser.add_argument(
        "--date-range",
        type=str,
        help="Required for a download run. Use 'YYYY' or 'YYYY-MM-DD:YYYY-MM-DD'."
    )
    parser.add_argument(
        "--output-directory",
        type=str,
        default="fiscal_fetch_output",
        help="The root directory for all outputs (logs, reports, downloads)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without downloading any files."
    )
    parser.add_argument(
        "--force-rescan",
        action="store_true",
        help="Ignore the processed threads index and re-scan all emails."
    )

    # New "reset" argument
    parser.add_argument(
        "--reset",
        type=str,
        nargs='?',
        const="all",
        help="Deletes downloaded files and resets the index for a given period. Use 'YYYY', 'YYYY-MM', or 'all'."
    )
    
    # New "report" argument
    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Extracts email data into a report and saves emails as .eml files."
    )

    args = parser.parse_args()
    config = vars(args)
    app = FiscalFetchCore(config)

    if args.reset:
        app.reset_period(args.reset)
    elif args.date_range:
        app.run()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
