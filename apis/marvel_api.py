import os
import time
import hashlib
import ssl
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

MARVEL_PUBLIC_KEY = os.getenv('MARVEL_PUBLIC_KEY')
MARVEL_PRIVATE_KEY = os.getenv('MARVEL_PRIVATE_KEY')

if not MARVEL_PUBLIC_KEY or not MARVEL_PRIVATE_KEY:
    print("Marvel API keys missing from your .env file.")

# Custom adapter to handle potential SSL issues
class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')  # Lower security level if needed
        kwargs['ssl_context'] = context
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

# Create a session with our custom TLS adapter
session = requests.Session()
session.mount('https://', TLSAdapter())

# Function to fetch Marvel character details by name
def fetch_marvel_character(character_name):
    try:
        ts = str(time.time())
        hash_input = f"{ts}{MARVEL_PRIVATE_KEY}{MARVEL_PUBLIC_KEY}"
        hash_result = hashlib.md5(hash_input.encode()).hexdigest()
        
        base_url = "https://gateway.marvel.com/v1/public/characters"
        params = {
            "name": character_name,
            "ts": ts,
            "apikey": MARVEL_PUBLIC_KEY,
            "hash": hash_result
        }
        response = session.get(base_url, params=params)
        if response.status_code != 200:
            print(f"Marvel API error: {response.status_code}")
            return []
        
        json_data = response.json()
        data = json_data.get("data", {})
        results_list = data.get("results", [])
        results = []
        for character in results_list:
            thumbnail = character.get("thumbnail")
            if thumbnail and thumbnail.get("path") and thumbnail.get("extension"):
                image_url = f"{thumbnail.get('path')}.{thumbnail.get('extension')}"
                results.append({
                    "name": character.get("name"),
                    "image": image_url,
                    "source": "marvel"
                })
        return results
    except Exception as e:
        print("Error fetching Marvel character:", e)
        return []
