import requests
import hashlib
import os
import time
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from dotenv import load_dotenv


# Load environment variables from the .env file
load_dotenv()

MARVEL_PUBLIC_KEY = os.getenv('MARVEL_PUBLIC_KEY')
MARVEL_PRIVATE_KEY = os.getenv('MARVEL_PRIVATE_KEY')

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')  # Lower security level
        kwargs['ssl_context'] = context
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

session = requests.Session()
session.mount('https://', TLSAdapter())

def fetch_marvel_character(character_name):
    try:
        ts = str(time.time())
        hash_input = f"{ts}{MARVEL_PRIVATE_KEY}{MARVEL_PUBLIC_KEY}"
        hash_result = hashlib.md5(hash_input.encode()).hexdigest()

        search_url = f"https://gateway.marvel.com/v1/public/characters?name={character_name}&apikey={MARVEL_PUBLIC_KEY}&ts={ts}&hash={hash_result}"
        search_response = session.get(search_url)  # Use custom session with SSL context

        if search_response.status_code == 200:
            search_results = search_response.json().get('data', {}).get('results', [])
            if search_results:
                character_id = search_results[0]['id']
                detail_url = f"https://gateway.marvel.com/v1/public/characters/{character_id}?apikey={MARVEL_PUBLIC_KEY}&ts={ts}&hash={hash_result}"
                detail_response = session.get(detail_url)

                if detail_response.status_code == 200:
                    character_data = detail_response.json().get('data', {}).get('results', [])[0]
                    name = character_data.get('name')
                    thumbnail = character_data.get('thumbnail', {})
                    image_url = f"{thumbnail.get('path')}.{thumbnail.get('extension')}"
                    return {name: image_url}
        return {}
    except Exception as e:
        print(f"Exception occurred while fetching Marvel character: {e}")
        return {}
