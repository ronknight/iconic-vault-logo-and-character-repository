import os
import json
import requests
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, send_file, flash
from dotenv import load_dotenv
from brandfetch import search_and_download_logo, search_brands, fetch_best_logo_for_domain
import pandas as pd
from apis.disney_api import fetch_disney_character
from apis.marvel_api import fetch_marvel_character
from apis.fandom_api import fetch_fandom_character

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# File paths
UPLOAD_FOLDER = 'static/logos'
CHARACTERS_FOLDER = 'static/characters'
BRANDS_FILE = 'brands.json'
CHARACTERS_FILE = 'characters.json'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure directories exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(CHARACTERS_FOLDER):
    os.makedirs(CHARACTERS_FOLDER)

if os.path.exists(BRANDS_FILE):
    with open(BRANDS_FILE, 'r') as f:
        brands_data = json.load(f)
else:
    brands_data = {}

if os.path.exists(CHARACTERS_FILE):
    with open(CHARACTERS_FILE, 'r') as f:
        temp = json.load(f)
    characters_data = {}
    for name, data in temp.items():
        if isinstance(data, str):
            characters_data[name] = {'image': data, 'source': 'unknown'}
        else:
            characters_data[name] = data
else:
    characters_data = {}

# Function to download and save character images
def download_image(image_url, character_name):
    try:
        parsed_url = urlparse(image_url)
        file_extension = os.path.splitext(parsed_url.path)[1]

        filename = f"{character_name.replace(' ', '_')}{file_extension}"
        file_path = os.path.join(CHARACTERS_FOLDER, filename)

        if not os.path.exists(file_path):
            response = requests.get(image_url)
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
            else:
                print(f"Failed to download image for {character_name}: {response.status_code}")
        return filename
    except Exception as e:
        print(f"Error downloading image for {character_name}: {e}")
        return None

# Favicon route
@app.route('/favicon.ico')
def favicon():
    favicon_path = os.path.join(app.root_path, 'static', 'favicon.ico')
    if os.path.exists(favicon_path):
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')
    else:
        return '', 204  # No Content

# Home route
@app.route('/')
def home():
    return render_template('home.html')

def make_pages(page, total_pages, window=2):
    start = max(1, page - window)
    end = min(total_pages, page + window)
    return list(range(start, end + 1))

# Brand Logos Route
@app.route('/logos', methods=['GET'])
def logos_page():
    query = request.args.get('q', '')
    sort_order = request.args.get('sort', 'asc')
    bf_query = request.args.get('bf', '').strip()
    # Pagination params (with safe defaults)
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get('per_page', 24))
    except ValueError:
        per_page = 24
    per_page = max(1, min(per_page, 200))  # clamp
    page = max(1, page)

    # Filter
    if query:
        filtered_logos = {logo: brand for logo, brand in brands_data.items() if query.lower() in brand.lower()}
    else:
        filtered_logos = brands_data

    # Sort
    if sort_order == 'asc':
        sorted_items = sorted(filtered_logos.items(), key=lambda item: item[1].lower())
    else:
        sorted_items = sorted(filtered_logos.items(), key=lambda item: item[1].lower(), reverse=True)

    # Pagination calculations
    total = len(sorted_items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    page_items = sorted_items[start:end]

    # Convert back to dict for template iteration convenience
    paged_logos = dict(page_items)

    # Optional Brandfetch search results
    brandfetch_results = []
    if bf_query:
        if not os.getenv('BRANDFETCH_API_KEY'):
            flash('Brandfetch API key not configured. Add BRANDFETCH_API_KEY to your .env.')
        
        # First search to get candidate domains, then fetch details with a best logo
        candidates = search_brands(bf_query, limit=8) or []
        for c in candidates[:8]:
            ident = c.get('domain') or c.get('website') or bf_query
            details = fetch_best_logo_for_domain(ident)
            if details and details.get('logo_url'):
                brandfetch_results.append({
                    'name': details.get('name') or c.get('name') or ident,
                    'domain': details.get('domain') or c.get('domain') or ident,
                    'logo_url': details['logo_url']
                })

    pages = make_pages(page, total_pages)

    # Range display (1-based)
    start_index = 0 if total == 0 else start + 1
    end_index = min(end, total)

    return render_template(
        'logos.html',
        logos=paged_logos,
        query=query,
        sort_order=sort_order,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        pages=pages,
        start_index=start_index,
        end_index=end_index,
        bf=bf_query,
        bf_results=brandfetch_results,
    )

@app.route('/import_brandfetch', methods=['POST'])
def import_brandfetch():
    brand_name = request.form.get('brand_name', '').strip()
    brand_domain = request.form.get('brand_domain', '').strip()
    if not brand_name or not brand_domain:
        flash('Missing brand information to import.')
        return redirect(url_for('logos_page'))
    # Use Brandfetch helper to download and save
    success = search_and_download_logo(brand_name, app.config['UPLOAD_FOLDER'], brand_domain)
    if success:
        filename = f"{brand_name}.svg"
        brands_data[filename] = brand_name
        with open(BRANDS_FILE, 'w') as f:
            json.dump(brands_data, f)
        flash(f"Imported logo for {brand_name} from Brandfetch.")
    else:
        flash(f"Failed to import logo for {brand_name}. Ensure BRANDFETCH_API_KEY is set and domain is correct.")
    return redirect(url_for('logos_page', bf=brand_domain))

# Upload brand logos via form
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files or 'brand_name' not in request.form:
        return redirect(request.url)

    file = request.files['file']
    brand_name = request.form['brand_name']

    if file.filename == '' or brand_name == '':
        return redirect(request.url)

    if file:
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
        brands_data[file.filename] = brand_name
        with open(BRANDS_FILE, 'w') as f:
            json.dump(brands_data, f)
        return redirect(url_for('logos_page'))

# Serve logo images
@app.route('/logos/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Download logo route
@app.route('/download/<filename>')
def download_logo(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# Delete logo route
@app.route('/delete_logo/<filename>', methods=['POST'])
def delete_logo(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        if filename in brands_data:
            del brands_data[filename]
            with open(BRANDS_FILE, 'w') as f:
                json.dump(brands_data, f)
        flash(f"Logo '{filename}' deleted successfully.")
    else:
        flash(f"Logo '{filename}' not found.")

    return redirect(url_for('logos_page'))

# Download Excel template
@app.route('/download_excel_template')
def download_excel_template():
    # Create a sample Excel file with headers and a sample row
    data = {
        'Brand': ['Example Brand'],
        'Domain': ['example.com']
    }
    df = pd.DataFrame(data)
    
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template')
    output.seek(0)
    
    return send_file(output, as_attachment=True, download_name='excel_upload_template.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Excel file upload for logos
@app.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            flash("No Excel file provided.")
            return redirect(request.url)

        excel_file = request.files['excel_file']

        if excel_file.filename == '':
            flash("No file selected.")
            return redirect(request.url)

        try:
            if excel_file.filename.lower().endswith('.csv'):
                df = pd.read_csv(excel_file)
            else:
                df = pd.read_excel(excel_file, engine='openpyxl')
        except Exception:
            try:
                if excel_file.filename.lower().endswith('.csv'):
                    df = pd.read_csv(excel_file)
                else:
                    df = pd.read_excel(excel_file, engine='xlrd')
            except Exception as e:
                flash(f"Error reading file: {e}")
                return redirect(request.url)

        if 'Brand' not in df.columns or 'Domain' not in df.columns:
            flash("File must have 'Brand' and 'Domain' columns.")
            return redirect(request.url)

        for index, row in df.iterrows():
            brand_name = row['Brand'].strip()
            brand_domain = row['Domain'].strip()

            logo_filename = f"{brand_name}.svg"
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)

            if os.path.exists(logo_path):
                print(f"Logo already exists for {brand_name}, skipping...")
                continue

            print(f"Downloading high-resolution logo for {brand_name} using Brandfetch API...")
            if search_and_download_logo(brand_name, app.config['UPLOAD_FOLDER'], brand_domain):
                brands_data[logo_filename] = brand_name
            else:
                print(f"Failed to download logo for {brand_name}")

        with open(BRANDS_FILE, 'w') as f:
            json.dump(brands_data, f)

        flash("Logos processed successfully from file.")
        return redirect(url_for('logos_page'))

    return render_template('upload_excel.html')

# Licensed Characters Route
@app.route('/characters', methods=['GET', 'POST'])
def characters_page():
    api_query = request.args.get('character_search', '')
    local_query = request.args.get('local_search', '')
    api_search_results = []  # list of formatted results
    combined_characters = characters_data

    # Get selected APIs from form/URL params
    selected_apis = request.args.getlist('apis') or request.form.getlist('apis')
    if not selected_apis:
        selected_apis = ['disney', 'marvel', 'fandom']  # Default to all

    if api_query:
        try:
            # Use the search_characters function to get results from selected APIs
            api_search_results = search_characters(api_query, selected_apis)
        except Exception as e:
            print(f"Error fetching characters: {e}")
            flash("Error fetching characters from APIs")

    if local_query:
        combined_characters = {character: data for character, data in characters_data.items()
                             if local_query.lower() in character.lower()}

    sort_order = request.args.get('sort', 'asc')

    # Pagination params
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get('per_page', 24))
    except ValueError:
        per_page = 24
    per_page = max(1, min(per_page, 200))
    page = max(1, page)

    sorted_items = sorted(
        combined_characters.items(), key=lambda item: item[0].lower(), reverse=(sort_order == 'desc')
    )

    total = len(sorted_items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    page_items = sorted_items[start:end]
    paged_characters = dict(page_items)

    pages = make_pages(page, total_pages)

    start_index = 0 if total == 0 else start + 1
    end_index = min(end, total)

    return render_template(
        'characters.html',
        characters=paged_characters,
        search_results=api_search_results,
        query=api_query,
        sort_order=sort_order,
        local_search=local_query,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        pages=pages,
        start_index=start_index,
        end_index=end_index,
    )

@app.route('/dashboard')
def dashboard():
    # Summary metrics
    logo_count = len(brands_data)
    char_count = len(characters_data)

    # Recent logos by mtime
    recent = []
    try:
        for fname, brand in brands_data.items():
            fpath = os.path.join(UPLOAD_FOLDER, fname)
            if os.path.exists(fpath):
                recent.append((fname, brand, os.path.getmtime(fpath)))
        recent = sorted(recent, key=lambda x: x[2], reverse=True)[:8]
    except Exception:
        recent = []

    # Sample characters (first 8 alphabetically)
    sample_chars = sorted([(name, data['image']) for name, data in characters_data.items()], key=lambda x: x[0].lower())[:8]

    return render_template('dashboard.html',
                           logo_count=logo_count,
                           char_count=char_count,
                           recent_logos=recent,
                           sample_characters=sample_chars)

@app.route('/add_character', methods=['POST'])
def add_character():
    character_name = request.form['character_name']
    image_url = request.form['image_url']
    source = request.form['source']

    local_image_filename = download_image(image_url, character_name)

    if local_image_filename:
        characters_data[character_name] = {'image': os.path.join(CHARACTERS_FOLDER, local_image_filename), 'source': source}
        with open(CHARACTERS_FILE, 'w') as f:
            json.dump(characters_data, f)
        flash(f"Character '{character_name}' added successfully.")
    else:
        flash(f"Failed to add character '{character_name}'.")

    # Preserve search parameters to maintain results and minimize API calls
    redirect_params = {}

    # Get current search parameters from the referrer or form data
    if request.referrer:
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(request.referrer)
        query_params = parse_qs(parsed_url.query)

        # Preserve search query
        if 'character_search' in query_params:
            redirect_params['character_search'] = query_params['character_search'][0]

        # Preserve local search
        if 'local_search' in query_params:
            redirect_params['local_search'] = query_params['local_search'][0]

        # Preserve selected APIs
        if 'apis' in query_params:
            redirect_params['apis'] = query_params['apis']

        # Preserve pagination and sorting
        if 'page' in query_params:
            redirect_params['page'] = query_params['page'][0]
        if 'per_page' in query_params:
            redirect_params['per_page'] = query_params['per_page'][0]
        if 'sort' in query_params:
            redirect_params['sort'] = query_params['sort'][0]

    return redirect(url_for('characters_page', **redirect_params))

@app.route('/delete_character/<character_name>', methods=['POST'])
def delete_character(character_name):
    if character_name in characters_data:
        del characters_data[character_name]
        with open(CHARACTERS_FILE, 'w') as f:
            json.dump(characters_data, f)
        flash(f"Character '{character_name}' deleted successfully.")
    else:
        flash(f"Character '{character_name}' not found.")

    # Preserve search parameters to maintain results and minimize API calls
    redirect_params = {}

    # Get current search parameters from the referrer
    if request.referrer:
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(request.referrer)
        query_params = parse_qs(parsed_url.query)

        # Preserve search query
        if 'character_search' in query_params:
            redirect_params['character_search'] = query_params['character_search'][0]

        # Preserve local search
        if 'local_search' in query_params:
            redirect_params['local_search'] = query_params['local_search'][0]

        # Preserve selected APIs
        if 'apis' in query_params:
            redirect_params['apis'] = query_params['apis']

        # Preserve pagination and sorting
        if 'page' in query_params:
            redirect_params['page'] = query_params['page'][0]
        if 'per_page' in query_params:
            redirect_params['per_page'] = query_params['per_page'][0]
        if 'sort' in query_params:
            redirect_params['sort'] = query_params['sort'][0]

    return redirect(url_for('characters_page', **redirect_params))

# Excel/CSV file upload for characters
@app.route('/upload_characters_excel', methods=['GET', 'POST'])
def upload_characters_excel():
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            flash("No file provided.")
            return redirect(request.url)

        file = request.files['excel_file']

        if file.filename == '':
            flash("No file selected.")
            return redirect(request.url)

        try:
            if file.filename.lower().endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
        except Exception as e:
            flash(f"Error reading file: {e}")
            return redirect(request.url)

        # Map columns
        char_col = 'LicensedCharacterName' if 'LicensedCharacterName' in df.columns else 'Character'
        img_col = 'imageUrl' if 'imageUrl' in df.columns else 'Image'

        if char_col not in df.columns or img_col not in df.columns:
            flash(f"File must have '{char_col}' and '{img_col}' columns.")
            return redirect(request.url)

        for index, row in df.iterrows():
            character_name = str(row[char_col]).strip()
            image_url = str(row[img_col]).strip()

            if not character_name or not image_url:
                continue

            if character_name in characters_data:
                print(f"Character {character_name} already exists, skipping...")
                continue

            local_image_filename = download_image(image_url, character_name)
            if local_image_filename:
                characters_data[character_name] = {'image': os.path.join(CHARACTERS_FOLDER, local_image_filename), 'source': 'upload'}
                print(f"Added {character_name} to the character repository.")

        with open(CHARACTERS_FILE, 'w') as f:
            json.dump(characters_data, f)

        flash("Characters processed successfully from file.")

        # Preserve search parameters to maintain results and minimize API calls
        redirect_params = {}

        # Get current search parameters from the referrer
        if request.referrer:
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(request.referrer)
            query_params = parse_qs(parsed_url.query)

            # Preserve search query
            if 'character_search' in query_params:
                redirect_params['character_search'] = query_params['character_search'][0]

            # Preserve local search
            if 'local_search' in query_params:
                redirect_params['local_search'] = query_params['local_search'][0]

            # Preserve selected APIs
            if 'apis' in query_params:
                redirect_params['apis'] = query_params['apis']

            # Preserve pagination and sorting
            if 'page' in query_params:
                redirect_params['page'] = query_params['page'][0]
            if 'per_page' in query_params:
                redirect_params['per_page'] = query_params['per_page'][0]
            if 'sort' in query_params:
                redirect_params['sort'] = query_params['sort'][0]

        return redirect(url_for('characters_page', **redirect_params))

    return render_template('upload_characters_excel.html')

# Download app.py file
@app.route('/download_app')
def download_app():
    return send_from_directory(app.root_path, 'app.py', as_attachment=True)

def search_characters(query, selected_apis=None):
    results = []

    if selected_apis is None:
        selected_apis = ['disney', 'marvel', 'fandom']

    # Get results from selected APIs
    if 'disney' in selected_apis:
        disney_results = fetch_disney_character(query)
        if isinstance(disney_results, dict):
            # Disney returns a mapping of name -> imageUrl
            for name, image in disney_results.items():
                if name and image:
                    results.append({
                        'name': str(name),
                        'image': str(image),
                        'source': 'disney'
                    })

    if 'marvel' in selected_apis:
        marvel_results = fetch_marvel_character(query)
        if isinstance(marvel_results, list):
            for result in marvel_results:
                if not isinstance(result, dict):
                    continue
                name = result.get('name')
                image = result.get('image')
                if name and image:
                    results.append({'name': name, 'image': image, 'source': 'marvel'})

    if 'fandom' in selected_apis:
        fandom_results = fetch_fandom_character(query)
        if isinstance(fandom_results, list):
            for result in fandom_results:
                if not isinstance(result, dict):
                    continue
                name = result.get('name')
                image = result.get('image')
                if name and image:
                    results.append({'name': name, 'image': image, 'source': 'fandom'})

    return results

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
