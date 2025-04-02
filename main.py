import os
import time
import json
from flask import Flask, redirect, request, render_template, send_from_directory
from google.cloud import storage
import google.generativeai as genai

app = Flask(__name__, template_folder='/home/abichishere/GoogleProject1/templates')

# Replace this with your original Gemini API key
GEMINI_API_KEY = 'AIzaSyB4FC8y9BEYXZ2Uv09eYj3qXAL_bKjk6NU'

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Set up Flask app and Google Cloud Storage client
app = Flask(__name__)
BUCKET_NAME = "project2bucketapi"
storage_client = storage.Client()

# Model configuration for Gemini
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

PROMPT = "describe the image. end your response in json"

def upload_to_gemini(path, mime_type=None):
    """Uploads the given file to Gemini."""
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file

def upload_to_bucket(bucket_name, file_path, file_name):
    """Uploads the given file to Google Cloud Storage bucket."""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.upload_from_filename(file_path)

@app.route('/upload', methods=["POST"])
def upload():
    """Handles file upload, saves the file, uploads it to Google Cloud Storage, and generates a description."""
    if 'form_file' not in request.files:
        return "No file part", 400  # Handle missing file in request

    file = request.files['form_file']
    
    if file.filename == '':
        return "No selected file", 400  # Handle empty filename

    # Save image temporarily to upload to Google Cloud Storage
    temp_image_path = os.path.join("/tmp", file.filename)
    file.save(temp_image_path)

    # Upload the image to Google Cloud Storage
    upload_to_bucket(BUCKET_NAME, temp_image_path, file.filename)

    # Upload to Gemini and generate description
    uploaded_file = upload_to_gemini(temp_image_path, mime_type="image/jpeg")
    response = model.generate_content(
        [uploaded_file, "\n\n", PROMPT]
    )

    # Remove the extension and add ".json"
    base_filename = os.path.splitext(file.filename)[0]  # Get the filename without the extension
    json_filename = f"{base_filename}.json"  # Add .json extension

    # Save the generated description to a JSON file
    description_data = {
        "title": file.filename,  # Keep the original filename for title
        "image": file.filename,
        "description": response.text,
        "timestamp": int(time.time())
    }

    # Define the path for the JSON file
    temp_json_path = os.path.join("/tmp", json_filename)  # Save JSON file temporarily

    # Save the JSON file
    with open(temp_json_path, 'w') as json_file:
        json.dump(description_data, json_file, indent=4)

    # Upload JSON file to Google Cloud Storage
    upload_to_bucket(BUCKET_NAME, temp_json_path, json_filename)

    # Clean up temporary files
    os.remove(temp_image_path)
    os.remove(temp_json_path)

    return redirect('/')

@app.route('/download/<filename>')
def download_json(filename):
    """Serves the generated JSON file from Google Cloud Storage."""
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    return redirect(blob.public_url)  # Redirect to the public URL of the file in Google Cloud Storage

@app.route('/files/<filename>')
def get_file(filename):
    """Serves the uploaded image file from Google Cloud Storage."""
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    return redirect(blob.public_url)  # Redirect to the public URL of the file in Google Cloud Storage

@app.route('/')
def index():
    index_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Image insert</title>
      </head>
      <body bgcolor="lightblue">
        <center><h1 class="title">To Upload or Not to Upload</h1></center>
        
        <div class="main_box">
          <h1>Upload Images Below</h1>
          <form method="post" enctype="multipart/form-data" action="/upload">
            <div>
              <label for="file">Choose file to upload</label>
              <input type="file" id="file" name="form_file" accept="image/jpeg"/>
            </div>
            <div>
              <button>Submit</button>
            </div>
          </form>

          <h2>Uploaded Files:</h2>
          <ul>
          """
    
    # List files from the cloud storage
    blobs = storage_client.bucket(BUCKET_NAME).list_blobs()
    for blob in blobs:
        if blob.name.lower().endswith(('.jpg', '.jpeg')):
            index_html += f'<li><a href="/files/{blob.name}">{blob.name}</a></li>'
    
    index_html += """
          </ul>
        </div>
      </body>
    </html>
    """

    return index_html

if __name__ == "__main__":
    app.run(debug=True)
