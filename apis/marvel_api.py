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
session.headers.update({'User-Agent': 'IconicVault/1.0'})
DEFAULT_TIMEOUT = 20

# Function to fetch Marvel character details by name
def _variant_url(thumbnail: dict, variant: str = 'portrait_uncanny') -> str:
    try:
        path = thumbnail.get('path', '')
        ext = thumbnail.get('extension', 'jpg')
        if not path:
            return ''
        # Ensure https
        if path.startswith('http://'):
            path = 'https://' + path[len('http://'):]
        # Build variant URL
        return f"{path}/{variant}.{ext}"
    except Exception:
        return ''


def fetch_marvel_character(character_name):
    try:
        ts = str(time.time())
        hash_input = f"{ts}{MARVEL_PRIVATE_KEY}{MARVEL_PUBLIC_KEY}"
        hash_result = hashlib.md5(hash_input.encode()).hexdigest()
        
        base_url = "https://gateway.marvel.com/v1/public/characters"
        params_exact = {
            "name": character_name,
            "ts": ts,
            "apikey": MARVEL_PUBLIC_KEY,
            "hash": hash_result
        }
        # First try exact match
        response = session.get(base_url, params=params_exact, timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            print(f"Marvel API error: {response.status_code}")
            return []
        
        json_data = response.json()
        data = json_data.get("data", {})
        results_list = data.get("results", [])
        results = []
        for character in results_list:
            thumbnail = character.get("thumbnail") or {}
            path = thumbnail.get('path', '')
            # Skip placeholders
            if not path or 'image_not_available' in path:
                continue
            image_url = _variant_url(thumbnail, 'portrait_uncanny')
            if not image_url:
                # Fallback to standard_large
                image_url = _variant_url(thumbnail, 'standard_large')
            if image_url:
                results.append({
                    "name": character.get("name"),
                    "image": image_url,
                    "source": "marvel"
                })

        if results:
            return results

        # Fallback: broader search by prefix if exact name produced nothing
        # Try multiple search strategies
        search_terms = [
            character_name,  # Full name
            character_name.split()[0] if character_name.split() else "",  # First word
            character_name.split()[-1] if len(character_name.split()) > 1 else ""  # Last word
        ]

        for search_term in search_terms:
            if not search_term:
                continue

            params_prefix = {
                "nameStartsWith": search_term[0].upper(),
                "limit": 100,
                "ts": ts,
                "apikey": MARVEL_PUBLIC_KEY,
                "hash": hash_result
            }
            response = session.get(base_url, params=params_prefix, timeout=DEFAULT_TIMEOUT)
            if response.status_code != 200:
                print(f"Marvel API error (prefix): {response.status_code}")
                continue

            json_data = response.json()
            data = json_data.get("data", {})
            results_list = data.get("results", [])

            for character in results_list:
                name = character.get("name", "")
                # Check if search term appears anywhere in the name (case-insensitive)
                if (character_name.lower() in name.lower() or
                    any(term.lower() in name.lower() for term in character_name.split())):
                    thumbnail = character.get("thumbnail") or {}
                    path = thumbnail.get('path', '')
                    if not path or 'image_not_available' in path:
                        continue
                    image_url = _variant_url(thumbnail, 'portrait_uncanny') or _variant_url(thumbnail, 'standard_large')
                    if image_url:
                        results.append({
                            "name": name,
                            "image": image_url,
                            "source": "marvel"
                        })

            # If we found results, return them
            if results:
                return results

        return results
    except Exception as e:
        print("Error fetching Marvel character:", e)
        return []
