# src/query_builder.py
from datetime import date

def parse_date_range(date_range_str: str) -> tuple[str, str] | None:
    """
    Parses a date range string into start and end dates.
    Supports "YYYY" and "YYYY-MM-DD:YYYY-MM-DD".
    """
    if ':' in date_range_str:
        try:
            start_str, end_str = date_range_str.split(':')
            date.fromisoformat(start_str)
            date.fromisoformat(end_str)
            return start_str.replace('-', '/'), end_str.replace('-', '/')
        except ValueError:
            print(f"Error: Invalid date format in '{date_range_str}'. Use YYYY-MM-DD:YYYY-MM-DD.")
            return None
    elif len(date_range_str) == 4 and date_range_str.isdigit():
        year = int(date_range_str)
        start_date = f"{year}/01/01"
        end_date = f"{year}/12/31"
        return start_date, end_date
    else:
        print(f"Error: Unsupported date range format '{date_range_str}'. Use 'YYYY' or 'YYYY-MM-DD:YYYY-MM-DD'.")
        return None

def build_query(profile_data: dict, date_range: str, user_email: str, user_inclusions: dict = None) -> str:
    """
    Builds a Gmail search query string from profile data and user inputs.
    """
    if user_inclusions is None:
        user_inclusions = {}

    include_keywords = list(set(profile_data.get('include_keywords', []) + user_inclusions.get('include_keywords', [])))
    from_senders = list(set(profile_data.get('from_senders', []) + user_inclusions.get('from_senders', [])))
    exclude_keywords = list(set(profile_data.get('exclude_keywords', []) + user_inclusions.get('exclude_keywords', [])))

    positive_parts = []
    if from_senders:
        sender_part = " OR ".join([f"from:{sender}" for sender in from_senders])
        positive_parts.append(f"{{{sender_part}}}")
    if include_keywords:
        keyword_part = " OR ".join([f'"{keyword}"' for keyword in include_keywords])
        positive_parts.append(keyword_part)

    query = f"({' OR '.join(positive_parts)})"

    if exclude_keywords:
        exclusion_part = " ".join([f'-"{keyword}"' for keyword in exclude_keywords])
        query += f" {exclusion_part}"

    parsed_dates = parse_date_range(date_range)
    if parsed_dates:
        start_date, end_date = parsed_dates
        query += f" after:{start_date} before:{end_date}"

    # Add final, more specific filters
    query += f" has:attachment -from:{user_email}"

    return query

if __name__ == '__main__':
    from profile_manager import load_profile
    print("--- Testing Query Builder ---")
    test_profile_data = load_profile('marketing-agency')
    test_date_range = "2024"
    test_user_email = "your.email@example.com"
    final_query = build_query(test_profile_data, test_date_range, test_user_email)
    print("\n--- Generated Gmail Query ---")
    print(final_query)
    print("-----------------------------\n")
