import requests
from urllib.parse import quote

def fetch_disney_character(name):
    try:
        url = f"https://api.disneyapi.dev/character?name={quote(name)}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()['data']
            if data:
                character = {
                    "name": data[0]['name'],
                    "image": data[0]['imageUrl']
                }
                return character
        return None
    except Exception as e:
        print(f"Error fetching Disney character: {e}")
        return None
