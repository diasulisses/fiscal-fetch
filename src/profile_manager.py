# src/profile_manager.py
import json
import os

def load_profile(profile_name: str) -> dict:
    """
    Loads the specified profile and merges it with the default profile.

    Args:
        profile_name: The name of the profile to load (e.g., 'marketing-agency').

    Returns:
        A dictionary containing the combined search criteria from the default
        and specified profiles.
    """
    profiles_dir = 'profiles'
    default_profile_path = os.path.join(profiles_dir, 'default.json')
    specific_profile_path = os.path.join(profiles_dir, f"{profile_name}.json")

    # Start with the default profile
    if os.path.exists(default_profile_path):
        with open(default_profile_path, 'r') as f:
            combined_profile = json.load(f)
    else:
        print(f"Warning: Default profile not found at {default_profile_path}")
        combined_profile = {"include_keywords": [], "from_senders": [], "exclude_keywords": []}

    # If a specific profile is requested, merge it in
    if profile_name and os.path.exists(specific_profile_path):
        with open(specific_profile_path, 'r') as f:
            specific_profile = json.load(f)
            # Merge lists, avoiding duplicates
            for key in combined_profile:
                if key in specific_profile:
                    combined_profile[key] = list(set(combined_profile[key] + specific_profile[key]))
    elif profile_name:
        print(f"Warning: Specific profile '{profile_name}' not found at {specific_profile_path}")

    return combined_profile

# --- Test block ---
if __name__ == '__main__':
    print("--- Testing Profile Manager ---")
    # This test now only READS the existing profile files.
    # It no longer overwrites them.

    # Check if profile files exist before running the test
    if not os.path.exists('profiles/default.json') or not os.path.exists('profiles/marketing-agency.json'):
        print("\nERROR: Profile files not found.")
        print("Please ensure 'profiles/default.json' and 'profiles/marketing-agency.json' exist before running the test.")
    else:
        print("\nLoading 'marketing-agency' profile...")
        profile_data = load_profile('marketing-agency')
        print("Loaded Profile Data:")
        print(json.dumps(profile_data, indent=2))

