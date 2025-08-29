import requests
import os
from urllib.parse import quote

BRANDFETCH_API_KEY = os.getenv('BRANDFETCH_API_KEY')
BRANDFETCH_URL = "https://api.brandfetch.io/v2/brands/"
BRANDFETCH_SEARCH_URL = "https://api.brandfetch.io/v2/search/"

def search_and_download_logo(brand_name, download_path, brand_domain=None):
    search_term = brand_domain if brand_domain else brand_name
    logo_file_path = os.path.join(download_path, f"{brand_name}.svg")

    if os.path.exists(logo_file_path):
        print(f"Logo for {brand_name} already exists, skipping download.")
        return False  # Skip API call if logo already exists

    try:
        headers = {
            'Authorization': f'Bearer {BRANDFETCH_API_KEY}'
        }

        url = f"{BRANDFETCH_URL}{quote(search_term)}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            if 'logos' in data and len(data['logos']) > 0:
                logo_url = None
                for format_data in data['logos'][0]['formats']:
                    if format_data['format'] == 'svg':
                        logo_url = format_data['src']
                        break
                if not logo_url:
                    logo_url = data['logos'][0]['formats'][0]['src']

                img_response = requests.get(logo_url, stream=True)
                if img_response.status_code == 200:
                    with open(logo_file_path, 'wb') as f:
                        for chunk in img_response.iter_content(1024):
                            f.write(chunk)
                    print(f"SVG Logo for {brand_name} downloaded successfully.")
                    return True
                else:
                    print(f"Error downloading logo for {brand_name}: {img_response.status_code}")
                    return False
            else:
                print(f"No logo found for {brand_name}")
                return False
        elif response.status_code == 404:
            print(f"Brandfetch did not find a match for {brand_name}")
            return False
        else:
            print(f"Error searching Brandfetch for {brand_name}: {response.status_code}")
            return False
    except Exception as e:
        print(f"Exception occurred during logo search and download for {brand_name}: {e}")
        return False

def _headers():
    return {'Authorization': f'Bearer {BRANDFETCH_API_KEY}'}

def search_brands(query, limit=10):
    """Search Brandfetch directory by name or domain.
    Returns a list of dicts with keys: name, domain, website.
    """
    if not BRANDFETCH_API_KEY:
        return []
    try:
        q = quote(query)
        url = f"{BRANDFETCH_SEARCH_URL}{q}?limit={int(limit)}"
        resp = requests.get(url, headers=_headers(), timeout=15)
        if resp.status_code != 200:
            return []
        items = resp.json() if isinstance(resp.json(), list) else []
        results = []
        for it in items:
            # Brandfetch returns keys like 'name', 'domain' and 'website'
            name = it.get('name') or it.get('legalName') or ''
            domain = it.get('domain') or (it.get('website') or '').replace('https://','').replace('http://','').split('/')[0]
            website = it.get('website') or (('https://' + domain) if domain else '')
            if domain or name:
                results.append({'name': name, 'domain': domain, 'website': website})
        return results
    except Exception:
        return []

def fetch_best_logo_for_domain(identifier):
    """Fetch brand details for a domain or query and pick a representative logo URL.
    Returns dict: {name, domain, logo_url} or None.
    """
    if not BRANDFETCH_API_KEY:
        return None
    try:
        url = f"{BRANDFETCH_URL}{quote(identifier)}"
        resp = requests.get(url, headers=_headers(), timeout=20)
        if resp.status_code != 200:
            return None
        data = resp.json()
        name = data.get('name') or data.get('brand') or ''
        domain = data.get('domain') or identifier
        logo_url = None
        # Prefer SVG, else first available format
        for logo in data.get('logos', []):
            formats = logo.get('formats', [])
            svg = next((f['src'] for f in formats if f.get('format') == 'svg'), None)
            if svg:
                logo_url = svg
                break
            if formats:
                logo_url = formats[0].get('src')
                # do not break; continue to try other logos for svg
        if not logo_url:
            return None
        return {'name': name, 'domain': domain, 'logo_url': logo_url}
    except Exception:
        return None
