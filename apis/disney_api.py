import requests
from urllib.parse import quote
import time
import os

# Cache for storing previously fetched characters
character_cache = {}

def fetch_disney_character(character_name):
    if character_name in character_cache:
        return character_cache[character_name]  # Return from cache if available
    
    try:
        url = f"https://api.disneyapi.dev/character?name={quote(character_name)}"
        retries = 3
        for attempt in range(retries):
            response = requests.get(url)

            if response.status_code == 200:
                results = response.json().get('data', [])
                if results:
                    character_data = {
                        result['name']: result['imageUrl']
                        for result in results
                    }
                    character_cache[character_name] = character_data  # Cache the result
                    return character_data
                else:
                    return {}  # No character found
            elif response.status_code == 429:
                print(f"Rate limited. Sleeping for 5 seconds...")
                time.sleep(5)
            else:
                print(f"Unexpected status {response.status_code} while fetching Disney character.")
                break

        return {}  # Return empty dictionary if no results
    except Exception as e:
        print(f"Error fetching Disney character: {e}")
        return {}  # Return empty dictionary on error
