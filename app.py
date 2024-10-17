import os
import json
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from dotenv import load_dotenv
from brandfetch import search_and_download_logo
from marvel import fetch_marvel_character
from disney import fetch_disney_character

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# File paths
UPLOAD_FOLDER = 'static/logos'
BRANDS_FILE = 'brands.json'
CHARACTERS_FILE = 'characters.json'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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

# Home route
@app.route('/')
def home():
    return render_template('home.html')

# Brand Logos Route
@app.route('/logos', methods=['GET'])
def logos_page():
    query = request.args.get('q', '')  # Search query for logos
    sort_order = request.args.get('sort', 'asc')  # Get the sorting order from the query parameters
    
    if query:
        filtered_logos = {logo: brand for logo, brand in brands_data.items() if query.lower() in brand.lower()}
    else:
        filtered_logos = brands_data

    # Sort logos based on the selected sort order
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
    query = request.args.get('character_search', '').strip()  # Search query for characters
    character = None
    if query:
        # First try fetching Disney character, then fall back to Marvel character
        character = fetch_disney_character(query) or fetch_marvel_character(query)

    if character:
        # Add to character repository if not already there
        if character['name'] not in characters_data:
            characters_data[character['name']] = character['image']
            with open(CHARACTERS_FILE, 'w') as f:
                json.dump(characters_data, f)
        flash(f"Found and saved character: {character['name']}")
    else:
        flash(f"No character found for: {query}")

    return render_template('characters.html', characters=characters_data)

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

            characters_data[character_name] = image_url
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
