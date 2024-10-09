import os
import json
import requests
import time
import mimetypes  # This helps to detect the file type
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import pandas as pd
from werkzeug.utils import secure_filename
from urllib.parse import quote
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
BRANDFETCH_API_KEY = os.getenv('BRANDFETCH_API_KEY')
BRANDFETCH_URL = "https://api.brandfetch.io/v2/brands/"

UPLOAD_FOLDER = 'static/logos'
BRANDS_FILE = 'brands.json'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if os.path.exists(BRANDS_FILE):
    with open(BRANDS_FILE, 'r') as f:
        brands_data = json.load(f)
else:
    brands_data = {}

# Function to save uploaded file with its original extension
def save_uploaded_file(file, brand_name):
    filename = secure_filename(file.filename)  # Ensure the filename is safe
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    # Add the file to the brand's data with its extension
    brands_data[filename] = brand_name
    with open(BRANDS_FILE, 'w') as f:
        json.dump(brands_data, f)

# Brandfetch API function to download logos with correct file extension
def search_and_download_logo(brand_name, download_path, brand_domain=None):
    search_term = brand_domain if brand_domain else brand_name
    try:
        headers = {'Authorization': f'Bearer {BRANDFETCH_API_KEY}'}
        url = f"{BRANDFETCH_URL}{quote(search_term)}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            if 'logos' in data and len(data['logos']) > 0:
                logo_url = None
                # Check for SVG first, otherwise fallback to the first available format
                for format_data in data['logos'][0]['formats']:
                    if format_data['format'] == 'svg':
                        logo_url = format_data['src']
                        break
                if not logo_url:
                    logo_url = data['logos'][0]['formats'][0]['src']
                
                # Get the file extension dynamically from the content type
                ext = mimetypes.guess_extension(requests.head(logo_url).headers.get('content-type'))
                logo_filename = f"{brand_name}{ext}"
                logo_path = os.path.join(download_path, logo_filename)

                # Download the logo
                img_response = requests.get(logo_url, stream=True)
                if img_response.status_code == 200:
                    with open(logo_path, 'wb') as f:
                        for chunk in img_response.iter_content(1024):
                            f.write(chunk)
                    print(f"Logo for {brand_name} downloaded successfully as {logo_filename}.")
                    return logo_filename
                else:
                    print(f"Error downloading logo for {brand_name}: {img_response.status_code}")
                    return None
            else:
                print(f"No logo found for {brand_name}")
                return None
        else:
            print(f"Error searching Brandfetch for {brand_name}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception occurred during logo search and download for {brand_name}: {e}")
        return None

# Serve logo images dynamically based on the actual file extension
@app.route('/logos/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Route to download logos
@app.route('/download/<filename>')
def download_logo(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# Route to upload logos manually
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files or 'brand_name' not in request.form:
        return redirect(request.url)
    
    file = request.files['file']
    brand_name = request.form['brand_name']
    
    if file.filename == '' or brand_name == '':
        return redirect(request.url)
    
    # Save the uploaded file with its original format
    save_uploaded_file(file, brand_name)
    return redirect(url_for('logos_page'))

# Route to delete logos
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

# Excel file upload route
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

        # Check if 'Brand' and 'Domain' columns exist
        if 'Brand' not in df.columns or 'Domain' not in df.columns:
            flash("Excel file must have 'Brand' and 'Domain' columns.")
            return redirect(request.url)

        # Process Excel data and handle logos upload
        for index, row in df.iterrows():
            brand_name = row['Brand'].strip()
            brand_domain = row['Domain'].strip()  # Use domain from the Excel sheet

            logo_filename = search_and_download_logo(brand_name, app.config['UPLOAD_FOLDER'], brand_domain)

            if logo_filename:
                # Only add to brands_data if the logo was newly downloaded or already exists
                if logo_filename not in brands_data:
                    brands_data[logo_filename] = brand_name
                    print(f"Added logo for {brand_name}")

            # Add a 10-second delay between downloads to respect API rate limits
            print("Waiting 10 seconds before the next download...")
            time.sleep(10)

        # Save the updated brands data
        with open(BRANDS_FILE, 'w') as f:
            json.dump(brands_data, f)

        flash("Logos processed successfully from Excel file.")
        return redirect(url_for('logos_page'))

    return render_template('upload_excel.html')

# Route for characters.html
@app.route('/characters')
def characters_page():
    return render_template('characters.html')

# Route for download_results.html
@app.route('/download_results')
def download_results_page():
    return render_template('download_results.html')

# Route for home.html
@app.route('/home')
def home_page():
    return render_template('home.html')

# Route for index.html (set as home route)
@app.route('/')
def index_page():
    query = request.args.get('q', '')  # Search query for logos
    logos = os.listdir(app.config['UPLOAD_FOLDER'])

    # Filter logos based on search query
    if query:
        filtered_logos = {logo: brand for logo, brand in brands_data.items() if query.lower() in brand.lower()}
    else:
        filtered_logos = brands_data

    return render_template('index.html', logos=filtered_logos, query=query)

# Route for logos.html
@app.route('/logos')
def logos_page():
    query = request.args.get('q', '')  # Search query for logos
    logos = os.listdir(app.config['UPLOAD_FOLDER'])
    
    # Filter logos based on search query
    if query:
        filtered_logos = {logo: brand for logo, brand in brands_data.items() if query.lower() in brand.lower()}
    else:
        filtered_logos = brands_data

    return render_template('logos.html', logos=filtered_logos, query=query)

# Route for match_results.html
@app.route('/match_results')
def match_results_page():
    return render_template('match_results.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
