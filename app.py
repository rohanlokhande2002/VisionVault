import math
import os
import shutil
import tempfile
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import boto3
import matplotlib.pyplot as plt
import requests
from flask import (Flask, flash, redirect, render_template, request, send_file,
                   session, url_for)
from PIL import Image
from werkzeug.utils import secure_filename

s3 = boto3.client('s3')
app = Flask(__name__)

app.secret_key = 'your_secret_key'
import secrets

bucket_name = 'rohantesting'
# Generate a secure random key
secret_key = secrets.token_hex(16)  # 16 bytes = 128 bits
print("Generated secret key:", secret_key)



@app.route("/", methods=['GET', 'POST'])
def home():
    folders = list_folders_in_bucket(bucket_name)
    if request.method == 'POST':
        selected_folder = request.form['selected_folder']
        session['selected_folder'] = selected_folder
        return redirect(url_for('find_similar_images'))
    else:
        selected_folder = session.get('selected_folder', '')
        return render_template('index.html', folders=folders, selected_folder=selected_folder)




@app.route('/about')
def about():
    return render_template('about.html')



# @app.route('/download_images', methods=['POST'])
# def download_images():
#     selected_images = request.form.getlist('selected_images')
#     print(f"Selected images are {selected_images}")
#     if selected_images:
#         # Create a temporary directory to store the downloaded images
#         temp_dir = 'temp_images'
#         os.makedirs(temp_dir, exist_ok=True)

#         # Download selected images and save them to the temporary directory
#         image_paths = []
#         for index, image_url in enumerate(selected_images):
#             response = requests.get(image_url)
#             if response.status_code == 200:
#                 image_path = os.path.join(temp_dir, f'image_{index}.jpg')
#                 with open(image_path, 'wb') as f:
#                     f.write(response.content)
#                 image_paths.append(image_path)

#         # Create a zip file containing the selected images
#         with ZipFile('selected_images.zip', 'w') as zipf:
#             for image_path in image_paths:
#                 zipf.write(image_path, os.path.basename(image_path))

#         # Send the zip file as a response for download
#         return send_file('selected_images.zip', as_attachment=True)
#     else:
#         return "No images selected."



@app.route('/download_images', methods=['POST'])
def download_images():
    selected_images = request.form.getlist('selected_images')
    if selected_images:
        # Create a temporary directory to store the downloaded images
        temp_dir = 'temp_images'
        os.makedirs(temp_dir, exist_ok=True)

        # Download selected images and save them to the temporary directory
        image_paths = []
        for index, image_url in enumerate(selected_images):
            response = requests.get(image_url)
            if response.status_code == 200:
                image_path = os.path.join(temp_dir, f'image_{index}.jpg')
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                image_paths.append(image_path)

        # Create a zip file containing the selected images
        with ZipFile('selected_images.zip', 'w') as zipf:
            for image_path in image_paths:
                zipf.write(image_path, os.path.basename(image_path))

        # Send the zip file as a response for download
        return send_file('selected_images.zip', as_attachment=True)
    else:
        return "No images selected."





# Route to handle the form submission for creating a new folder in S3
@app.route('/create_folder_and_upload_to_s3', methods=['POST'])
def create_folder_and_upload_to_s3():
    if request.method == 'POST':
        # Get the new folder name from the form
        new_folder_name = request.form['new_folder_name']

        # Create a new folder in the S3 bucket
        s3_client = boto3.client('s3')
        s3_client.put_object(Bucket=bucket_name, Key=new_folder_name + '/')

        # Set the newly created folder name in the session
        session['new_folder_name'] = new_folder_name
        print(session['new_folder_name'])

        # Set session variable to indicate folder creation
        session['folder_created'] = True
        
        # Redirect back to the home page
        return redirect(url_for('home'))
    else:
        return "Method not allowed", 405




@app.route('/upload_content_to_s3', methods=['POST'])
def upload_content_to_s3():
    # Check if the folder was created in the session
    if 'folder_created' in session and session['folder_created']:
        # Get the newly created folder name from the session
        new_folder_name = session['new_folder_name']

        # Get the uploaded folder from the request
        uploaded_files = request.files.getlist('folder_content')

        # Get the S3 client
        s3 = boto3.client('s3')
        bucket_name = 'rohantesting'

        # Iterate over the uploaded files
        for uploaded_file in uploaded_files:
            # Ensure the filename is secure
            filename = secure_filename(uploaded_file.filename)

            # Construct the S3 key using the filename and new folder name
            s3_key = f"{new_folder_name}/{filename}"

            # Upload the file to S3
            s3.upload_fileobj(uploaded_file, bucket_name, s3_key)
            flash('Files uploaded to S3 successfully!', 'success')

        return redirect(url_for('home'))
    else:
        return "No folder created. Please create a folder first."




def list_folders_in_bucket(bucket_name):
    response = s3.list_objects_v2(Bucket=bucket_name, Delimiter='/')
    folders = [prefix.get('Prefix') for prefix in response.get('CommonPrefixes', [])]
    return folders



def download_and_display_images(s3_client, bucket_name, keys, similarities):
    # Calculate the number of rows and columns for the subplot grid
    num_images = len(keys)
    num_cols = 3  # Choose the number of columns you want in your grid
    num_rows = math.ceil(num_images / num_cols)

    # Create a figure with a grid of subplots
    fig, axes = plt.subplots(num_rows, num_cols, figsize=(15, 15))

    # Flatten the axes array for easier indexing
    axes = axes.flatten()

    # Iterate through the keys and similarities
    for i, (key, similarity) in enumerate(zip(keys, similarities)):
        # Debug print statement to check the key value
        print(f"Attempting to get object from S3 with key: {key}")

        # Construct the full key (including prefix if needed)
        full_key = f"search-images/{key}" if not key.startswith("search-images/") else key

        # Download the image from S3
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=full_key)
            image_data = response['Body'].read()

            # Open the image using PIL
            image = Image.open(BytesIO(image_data))

            # Display the image on the corresponding subplot
            axes[i].imshow(image)
            axes[i].set_title(f'Image: {key.replace("search-images/", "")}\nSimilarity: {similarity:.2f}%')
            axes[i].axis('off')  # Hide axes

        except Exception as e:
            print(f"Error retrieving image with key {full_key}: {e}")

    # Hide any empty subplots in the grid (if any)
    for j in range(num_images, len(axes)):
        axes[j].axis('off')

    # Show all images simultaneously
    plt.tight_layout()
    plt.show()



def compare_faces(source_bucket, source_key, target_bucket, target_key):
    rekognition = boto3.client('rekognition')
    source_image = {'S3Object': {'Bucket': source_bucket, 'Name': source_key}}
    target_image = {'S3Object': {'Bucket': target_bucket, 'Name': target_key}}
    response = rekognition.compare_faces(SourceImage=source_image, TargetImage=target_image)
    return response




def normalize_path(file_path):
    return file_path.replace("\\", "/")




def upload_image_to_s3(s3_client, bucket_name, image_path):
    # Generate a unique key for the uploaded image
    unique_key = str(uuid.uuid4())

    # Upload the image to the specified S3 bucket
    s3_client.upload_file(image_path, bucket_name, unique_key)
    return unique_key




def delete_image_from_s3(s3_client, bucket_name, key):
    # Delete the object from the S3 bucket
    s3_client.delete_object(Bucket=bucket_name, Key=key)






# Modify the find_similar_images() function
@app.route('/find_similar_images', methods=['POST'])
def find_similar_images():
    selected_folder = session.get('selected_folder', '')
    bucket_name = 'rohantesting'
    if request.method == 'POST':
        selected_folder = request.form['selected_folder']
        if selected_folder:
            # Construct the S3 prefix based on the selected folder
            folders = list_folders_in_bucket(bucket_name)
            prefix = f'{selected_folder}'
            print(prefix)
            image_file = request.files['image']
            if image_file:
                # Ensure that the 'temp' directory exists
                temp_dir = 'temp'
                Path(temp_dir).mkdir(parents=True, exist_ok=True)

                # Save the image file to the 'temp' directory
                image_path = os.path.join(temp_dir, image_file.filename)
                image_file.save(image_path)

                # Normalize the image path
                image_path = normalize_path(image_path)
                s3 = boto3.client('s3')
                # Your S3 bucket details
                bucket_name = 'rohantesting'
                source_bucket = 'rohantesting'
                target_bucket = 'rohantesting'

                target_key = upload_image_to_s3(s3, target_bucket, image_path)

                # List all objects in the 'search-images' folder in the bucket
                response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

                # Initialize lists to store image names and similarities
                image_names = []
                similarities = []
                image_urls = []  # Store image URLs in a list

                if 'Contents' in response:
                    # Iterate over each object in the bucket
                    for obj in response['Contents']:
                        # Get the object key (i.e., the file name)
                        key = obj['Key']

                        # Perform a face comparison if the file is an image
                        if key.endswith(('.jpg', '.jpeg', '.png', '.gif', 'JPG')):
                            # Call Rekognition compare_faces function
                            result = compare_faces(source_bucket, target_key, bucket_name, key)

                            # Check for face matches
                            if 'FaceMatches' in result:
                                # Iterate through each face match and store similarity confidence
                                for match in result['FaceMatches']:
                                    similarity = match['Similarity']

                                    # Check similarity threshold (e.g., >= 80)
                                    if similarity >= 80:
                                        # Append the image key and similarity to the lists
                                        image_urls.append(f"https://{bucket_name}.s3.amazonaws.com/{obj['Key']}")
                                        image_names.append(obj)
                                        similarities.append(similarity)

                # Store the list of image URLs in the session
                session['image_urls'] = image_urls

                # Delete the uploaded target image from the S3 bucket
                delete_image_from_s3(s3, target_bucket, target_key)

                # Render the template with image URLs
                return render_template('index.html', folders=folders, selected_folder=selected_folder, image_urls=image_urls)
        else:
            return "No folder selected."
    else:
        return "Method not allowed", 405





# Modify the download_all_images() function
@app.route('/download_all_images', methods=['POST'])
def download_all_images():
    # Retrieve the list of image URLs from the session
    image_urls = session.get('image_urls', [])

    if image_urls:
        # Create a temporary directory to store the downloaded images
        temp_dir = 'temp_images'
        os.makedirs(temp_dir, exist_ok=True)

        # Download all images to the temporary directory
        image_paths = []
        for index, image_url in enumerate(image_urls):
            response = requests.get(image_url)
            if response.status_code == 200:
                image_path = os.path.join(temp_dir, f'image_{index}.jpg')
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                image_paths.append(image_path)

        # Create a zip file containing the downloaded images
        with zipfile.ZipFile('all_images.zip', 'w') as zipf:
            for image_path in image_paths:
                zipf.write(image_path, os.path.basename(image_path))

        # Send the zip file as a response for download
        return send_file('all_images.zip', as_attachment=True)
    else:
        return "No images to download."




if __name__ == "__main__":
    app.run(debug=True)



# https://www.youtube.com/watch?v=4zrupVYqQFs