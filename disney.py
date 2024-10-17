import requests
from urllib.parse import quote

def fetch_disney_character(character_name):
    try:
        url = f"https://api.disneyapi.dev/character?name={character_name}"
        response = requests.get(url)

        if response.status_code == 200:
            results = response.json().get('data', [])
            if results:
                # Return a dictionary with name and image
                return {
                    result['name']: result['imageUrl']
                    for result in results
                }
        return {}  # Return empty dictionary if no results
    except Exception as e:
        print(f"Error fetching Disney character: {e}")
        return {}  # Return empty dictionary on error

