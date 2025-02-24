import os
import json
import requests
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from dotenv import load_dotenv
from brandfetch import search_and_download_logo
import pandas as pd
from apis.disney_api import fetch_disney_character
from apis.marvel_api import fetch_marvel_character
from apis.fandom_api import fetch_fandom_character

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

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
        characters_data = json.load(f)
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

# Home route
@app.route('/')
def home():
    return render_template('home.html')

# Brand Logos Route
@app.route('/logos', methods=['GET'])
def logos_page():
    query = request.args.get('q', '')
    sort_order = request.args.get('sort', 'asc')
    
    if query:
        filtered_logos = {logo: brand for logo, brand in brands_data.items() if query.lower() in brand.lower()}
    else:
        filtered_logos = brands_data

    if sort_order == 'asc':
        sorted_logos = dict(sorted(filtered_logos.items(), key=lambda item: item[1].lower()))
    else:
        sorted_logos = dict(sorted(filtered_logos.items(), key=lambda item: item[1].lower(), reverse=True))

    return render_template('logos.html', logos=sorted_logos, query=query, sort_order=sort_order)

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
            df = pd.read_excel(excel_file)
        except Exception as e:
            flash(f"Error reading Excel file: {e}")
            return redirect(request.url)

        if 'Brand' not in df.columns or 'Domain' not in df.columns:
            flash("Excel file must have 'Brand' and 'Domain' columns.")
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

        flash("Logos processed successfully from Excel file.")
        return redirect(url_for('logos_page'))

    return render_template('upload_excel.html')

# Licensed Characters Route
@app.route('/characters', methods=['GET', 'POST'])
def characters_page():
    api_query = request.args.get('character_search', '')  
    local_query = request.args.get('local_search', '')   
    api_search_results = []  # Changed to list for formatted results
    combined_characters = characters_data  

    if api_query:
        try:
            # Use the search_characters function to get results from all APIs
            api_search_results = search_characters(api_query)
        except Exception as e:
            print(f"Error fetching characters: {e}")
            flash("Error fetching characters from APIs")

    if local_query:
        combined_characters = {character: image for character, image in characters_data.items() 
                             if local_query.lower() in character.lower()}

    sort_order = request.args.get('sort', 'asc')
    sorted_characters = dict(sorted(combined_characters.items(), 
                                  key=lambda item: item[0].lower(), 
                                  reverse=(sort_order == 'desc')))

    return render_template('characters.html', 
                         characters=sorted_characters, 
                         search_results=api_search_results, 
                         query=api_query, 
                         sort_order=sort_order, 
                         local_search=local_query)

@app.route('/add_character', methods=['POST'])
def add_character():
    character_name = request.form['character_name']
    image_url = request.form['image_url']

    local_image_filename = download_image(image_url, character_name)

    if local_image_filename:
        characters_data[character_name] = os.path.join(CHARACTERS_FOLDER, local_image_filename)
        with open(CHARACTERS_FILE, 'w') as f:
            json.dump(characters_data, f)
        flash(f"Character '{character_name}' added successfully.")
    else:
        flash(f"Failed to add character '{character_name}'.")

    return redirect(url_for('characters_page'))

@app.route('/delete_character/<character_name>', methods=['POST'])
def delete_character(character_name):
    if character_name in characters_data:
        del characters_data[character_name]
        with open(CHARACTERS_FILE, 'w') as f:
            json.dump(characters_data, f)
        flash(f"Character '{character_name}' deleted successfully.")
    else:
        flash(f"Character '{character_name}' not found.")
    return redirect(url_for('characters_page'))

# Excel file upload for characters
@app.route('/upload_characters_excel', methods=['GET', 'POST'])
def upload_characters_excel():
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            flash("No Excel file provided.")
            return redirect(request.url)

        excel_file = request.files['excel_file']

        if excel_file.filename == '':
            flash("No file selected.")
            return redirect(request.url)

        try:
            df = pd.read_excel(excel_file)
        except Exception as e:
            flash(f"Error reading Excel file: {e}")
            return redirect(request.url)

        if 'Character' not in df.columns or 'Image' not in df.columns:
            flash("Excel file must have 'Character' and 'Image' columns.")
            return redirect(request.url)

        for index, row in df.iterrows():
            character_name = row['Character'].strip()
            image_url = row['Image'].strip()

            if character_name in characters_data:
                print(f"Character {character_name} already exists, skipping...")
                continue

            local_image_filename = download_image(image_url, character_name)
            if local_image_filename:
                characters_data[character_name] = os.path.join(CHARACTERS_FOLDER, local_image_filename)
                print(f"Added {character_name} to the character repository.")

        with open(CHARACTERS_FILE, 'w') as f:
            json.dump(characters_data, f)

        flash("Characters processed successfully from Excel file.")
        return redirect(url_for('characters_page'))

    return render_template('upload_characters_excel.html')

# Download app.py file
@app.route('/download_app')
def download_app():
    return send_from_directory(app.root_path, 'app.py', as_attachment=True)

def search_characters(query):
    results = []
    
    # Get results from each API
    disney_results = fetch_disney_character(query)
    marvel_results = fetch_marvel_character(query)
    fandom_results = fetch_fandom_character(query)
    
    # Now each API is expected to return a list of dictionaries.
    for api_results in [disney_results, marvel_results, fandom_results]:
        if isinstance(api_results, list):
            # Each result should be a dict with keys 'name', 'image', and 'source'
            for result in api_results:
                # Sanity-check that result is a dict
                if isinstance(result, dict):
                    results.append(result)
        elif isinstance(api_results, dict):
            results.append(api_results)
    
    return results

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
