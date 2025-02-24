import requests
from urllib.parse import quote

class FandomAPI:
    def __init__(self):
        self.character_cache = {}
        
    def search_character(self, query):
        query_lower = query.lower().strip()
        if query_lower in self.character_cache:
            return self.character_cache[query_lower]
        
        results = []
        page = 1
        total_pages = 1  # Will be updated after the first request
        
        while page <= total_pages:
            try:
                url = f"https://api.disneyapi.dev/character?name={quote(query)}&page={page}"
                response = requests.get(url)
                if response.status_code != 200:
                    print(f"Error fetching from Disney API (page {page}): {response.status_code}")
                    break
                    
                json_data = response.json()
                if not isinstance(json_data, dict):
                    print("Unexpected response format:", json_data)
                    break
                
                # Update total_pages based on the response after the first call
                total_pages = json_data.get("totalPages", 1)
                
                data = json_data.get("data", [])
                for character in data:
                    if not isinstance(character, dict):
                        continue
                    image_url = character.get("imageUrl")
                    if image_url:
                        results.append({
                            "name": character.get("name"),
                            "image": image_url,
                            "source": "disney"
                        })
            except Exception as e:
                print(f"Disney API error on page {page}: {e}")
                break
            page += 1
        
        if results:
            self.character_cache[query_lower] = results
            return results
        
        return []

def fetch_fandom_character(character_name):
    """Wrapper function to match Disney and Marvel API patterns"""
    api = FandomAPI()
    return api.search_character(character_name)