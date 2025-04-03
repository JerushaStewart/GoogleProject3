should it look like this: import os
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

def list_files_from_bucket(bucket_name):
    """Lists image files in the Google Cloud Storage bucket."""
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs()
    return [blob.name for blob in blobs if blob.name.lower().endswith(('.jpg', '.jpeg'))]

@app.route('/')
def index():
    index_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Image insert</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Style+Script&display=swap" rel="stylesheet">
        <link href="/style.css" rel="stylesheet" type="text/css" media="all">
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
    files = list_files_from_bucket(BUCKET_NAME)
    for file in files:
        index_html += f'<li><a href="/view/{file}">{file}</a></li>'
    
    index_html += """
          </ul>
        </div>
         <style>
    * {
      margin: 0;
      padding: 0;
    }

    li {
      list-style-type: none;
    }

    body {
      background-color: white;
    }

    .title {
      font-family: "Style Script", serif;
      font-weight: 400;
      font-style: bold;
      font-size: 50px;
      color: #ff62bf;
    }

    .main_box {
      border-radius: 5px;
      border: 5px solid #ff62bf;
      background-color: pink;
      margin: 10px 200px 0 200px;
      padding: 25px;
    }

    h1 {
      font-size: 20px;
      font-weight: bold;
    }

    .box {
      border: 1px solid black;
    }

    a {
      text-decoration: none; 
    }

    </style> 
      </body>
    </html>
    """

    return index_html

@app.route('/view/<filename>')
def view_file(filename):
    """Serve the image file and its description."""
    # Generate the path for the file
    json_filename = os.path.splitext(filename)[0] + '.json'  # Assuming JSON exists for this file
    
    # Attempt to load the description from the JSON file
    description_data = None
    try:
        # Fetch JSON data from Cloud Storage
        blob = storage_client.bucket(BUCKET_NAME).blob(json_filename)
        json_content = blob.download_as_text()
        description_data = json.loads(json_content)
    except Exception as e:
        print(f"Error retrieving JSON file: {e}")
    
    return render_template(
        "view_file.html",  # You can create a view_file.html template to show details
        filename=filename,
        description_data=description_data
    )

@app.route('/upload', methods=["POST"])
def upload():
    """Handles file upload, uploads the file to Google Cloud Storage, and generates a description."""
    if 'form_file' not in request.files:
        return "No file part", 400  # Handle missing file in request

    file = request.files['form_file']
    
    if file.filename == '':
        return "No selected file", 400  # Handle empty filename

    # Save the file temporarily to upload it to Google Cloud Storage
    temp_image_path = os.path.join("/tmp", file.filename)
    file.save(temp_image_path)

    # Upload the image to Google Cloud Storage
    upload_to_bucket(BUCKET_NAME, temp_image_path, file.filename)

    # Upload to Gemini and generate a description
    uploaded_file = upload_to_gemini(temp_image_path, mime_type="image/jpeg")
    response = model.generate_content(
        [uploaded_file, "\n\n", PROMPT]
    )

    # Generate a default title based on the first sentence of the response description
    description = response.text.strip()
    default_title = description.split('.')[0]  # Get the first sentence as the title

    # If no title is extracted, fall back to a default string based on the image filename
    if not default_title:
        default_title = f"Description of {file.filename}"

    # Remove the extension and add ".json"
    base_filename = os.path.splitext(file.filename)[0]  # Get the filename without the extension
    json_filename = f"{base_filename}.json"  # Add .json extension

    # Save the generated description to a JSON file
    description_data = {
        "title": default_title,  # Use the generated description as the title
        "image": file.filename,
        "description": description,
        "timestamp": int(time.time())
    }

    # Save the JSON to Google Cloud Storage
    json_content = json.dumps(description_data, indent=4)
    blob = storage_client.bucket(BUCKET_NAME).blob(json_filename)
    blob.upload_from_string(json_content, content_type="application/json")

    # Clean up temporary files
    os.remove(temp_image_path)

    return redirect('/')


@app.route('/download/<filename>')
def download_json(filename):
    """Serves the generated JSON file from Google Cloud Storage."""
    blob = storage_client.bucket(BUCKET_NAME).blob(filename)
    return redirect(blob.public_url)  # Redirect to the public URL of the file in Google Cloud Storage

@app.route('/files/<filename>')
def get_file(filename):
    """Serves the uploaded image file."""
    return send_from_directory('./files', filename)

if __name__ == "__main__":
    app.run(debug=True)
