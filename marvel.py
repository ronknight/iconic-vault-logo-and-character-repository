import requests
import hashlib
import time
import os
import certifi

MARVEL_PUBLIC_KEY = os.getenv('MARVEL_PUBLIC_KEY')
MARVEL_PRIVATE_KEY = os.getenv('MARVEL_PRIVATE_KEY')

def fetch_marvel_character(name):
    try:
        ts = str(time.time())
        hash_input = f"{ts}{MARVEL_PRIVATE_KEY}{MARVEL_PUBLIC_KEY}"
        hash_result = hashlib.md5(hash_input.encode()).hexdigest()
        url = f"https://gateway.marvel.com/v1/public/characters?name={name}&apikey={MARVEL_PUBLIC_KEY}&ts={ts}&hash={hash_result}"
        response = requests.get(url, verify=certifi.where())  # Use a custom certificate bundle
        if response.status_code == 200:
            data = response.json()['data']['results']
            if data:
                character = {
                    "name": data[0]['name'],
                    "image": f"{data[0]['thumbnail']['path']}.{data[0]['thumbnail']['extension']}"
                }
                return character
        return None
    except Exception as e:
        print(f"Exception occurred while fetching Marvel character: {e}")
        return None
