#!/bin/python
import base64
import json
from sqlite3 import sqlite_version

import ollama
from dotenv.cli import stream_file
from flask import Flask, request, send_file, jsonify, render_template, send_from_directory
from flask_cors import CORS
import threading
from pathlib import Path

from httpx import stream
from pydantic import BaseModel
import chromadb
import os
import re
from PIL import Image, ExifTags
import sqlite3
import datetime
import stat

app = Flask(__name__)
CORS(app)

global thread_locked, processed_files, embedding_model, vector_db_path, sqlite_path,  temperature, vision_model, chroma_client

vision_model = "llama3.2-vision:11b-instruct-q8_0"
embedding_model = "nomic-embed-text:latest"
temperature = 1.31
1
chroma_path = os.path.join("db","ollimca_chroma.db")
sqlite_path = os.path.join("db","ollimca_sqlite3.db")
processed_files = []
thread_locked = False
chroma_client = None

class ImageDescription(BaseModel):
    description: str
    mood: str
    intent: str
    overall_color_scheme: str

def setup_sqlite():
    conn = sqlite3.connect(sqlite_path)

    # Create a cursor object using the connection
    cursor = conn.cursor()

    # Check if table exists, if not, create it
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT,
        width INTEGER,
        height INTEGER,
        content TEXT,
        creation_date TEXT
    )
    ''')
    conn.commit()
    conn.close()

def push_to_sqlite(image_path, image_description):
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    # Data to be inserted
    #print(image_description.keys())
    data = (image_path, image_description["width"], image_description["height"], image_description["creation_date"])
    # Insert data into the table
    cursor.execute('''
    INSERT INTO images (path, width, height, creation_date)
    VALUES (?, ?, ?, ?)
    ''', data)

    # Retrieve the last inserted row's ID
    new_id = cursor.lastrowid

    # Commit changes and close connection
    conn.commit()
    conn.close()
    return new_id

def update_content_in_sqlite(id, content):
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    # Data to be inserted
    data = (content, id)
    # Insert data into the table
    cursor.execute('''
    UPDATE images SET content=?
    WHERE id=?
    ''', data)

    # Commit changes and close connection
    conn.commit()
    conn.close()
    return

def fill_processed_files():
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    cursor.execute('SELECT path FROM images')
    paths = cursor.fetchall()
    return [row[0] for row in paths]
    conn.close()

def push_to_chroma(dbid, image_path, description):
    fulltext="description: "+description.description+"\nmood: "+description.mood+"\nintent: "+description.intent+"\ncolor_scheme: "+description.overall_color_scheme
    print(fulltext)
    description_as_dict = {
        "description":description.description,
        "mood":description.mood,
        "intent":description.intent,
        "color_scheme":description.overall_color_scheme
    }
    collection = chroma_client.get_or_create_collection('images')
    response = ollama.embeddings(model=embedding_model, prompt=fulltext, keep_alive=-1, options={ temperature:0})
    embedding = response['embedding']
    collection.add(ids=str(dbid), embeddings=embedding, documents=str(image_path), metadatas=description_as_dict)

def get_creation_time(image_path):
    try:
        # Get the status of the file
        stat_info = os.stat(image_path)

        # Check if st_birthtime is available (Python 3.8+ and supported file system)
        if hasattr(stat_info, 'st_birthtime'):
            creation_time = stat_info.st_birthtime
        else:
            # Fallback to st_mtime (modification time) if st_birthtime is not available
            creation_time = stat_info.st_mtime

        # Convert to a readable format
        return datetime.datetime.fromtimestamp(creation_time).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return f"Error: {e}"

def describe_and_store_image(str_image_path,dbid):
    image_path = Path(str_image_path)

    # Set up chat as usual
    response = ollama.chat (
        model=vision_model,
        format=ImageDescription.model_json_schema(),  # Pass in the schema for the response
        messages=[
            {
                'role': 'user',
                'content': 'Tell me the following about this image, be as detailed as possible: description, mood, intent, color names of the overall color scheme.',
                'images': [image_path],
            },
        ],
        options={
            'temperature': temperature,
            'keep_alive': -1
        },
        stream=False,
    )
    answer = ImageDescription.model_validate_json(response.message.content)
    push_to_chroma(dbid,str_image_path, answer)
    return answer.description

def store_meta(image_path):
    image = Image.open(image_path)
    exif = {}
    if image._getexif() != None:
        exif = {
            ExifTags.TAGS[k]: v
            for k, v in image._getexif().items()
            if k in ExifTags.TAGS
        }
        exif['MakerNote'] = ""
        exif['PrintImageMatching'] = ""
        exif['ComponentsConfiguration'] = ""
    else:
        exif = {}

    width = image.width
    height = image.height
    creation_date = ""
    if "DateTime" in exif and exif['DateTime'] != None and exif['DateTime'].strip() != "":
        creation_date = exif['DateTime'].strip()
    else:
        creation_date = get_creation_time(image_path)

    data = { "width": width,
             "height": height,
             "creation_date": creation_date
             }
    dbid = push_to_sqlite(image_path, data)
    return dbid

def file_generator(directory_path):
        global processed_files
        thread_locked = True
        pattern = re.compile(r'.*.(jpg|jpeg|png)$', re.IGNORECASE)
        processed_files = fill_processed_files()
        try:
            for root, _, files in os.walk(directory_path):
                for file in files:
                    if pattern.match(file):
                        file_path = os.path.join(root, file)
                        print("Processing file: " + file_path)
                        if file_path in processed_files:
                            continue
                        try:
                            dbid = store_meta(file_path)
                            content = describe_and_store_image(file_path, dbid)
                            update_content_in_sqlite(dbid, content)
                        except Exception as e:
                            print(e)
                        processed_files.append(file_path)
        except Exception as e:
            thread_locked = False
            print(f"Error processing directory: {str(e)}\n")
        thread_locked = False

@app.route('/api/query', methods=['POST'])
def find_images():
    data = request.get_json()
    content = data.get('content')
    mood = data.get('mood')
    colors = data.get('color')
    page = data.get('page')
    items_per_page = data.get('items_per_page')

    search_query = ""
    if content.strip() != "":
        search_query += "description:\""+content+"\""
    if mood.strip() != "":
        search_query += "\nmood:\""+mood+"\""
    if colors.strip() != "":
        search_query += "\ncolors:\""+colors+"\""

    response =ollama.embeddings(
        prompt=search_query,
        model=embedding_model,
        keep_alive=-1
    )
    client = chromadb.PersistentClient(chroma_path)
    collection = client.get_or_create_collection(name='images')
    results = collection.query(
        query_embeddings = [response['embedding']],
        n_results = (page*items_per_page),
    )
    images = []
    if len(results) > 0:
        cutoff = items_per_page * (page - 1)
        if cutoff > 0:
            documents = results["documents"][0][cutoff:]
        else:
            documents = results["documents"][0]
        for document in documents:
            images.append(document)
    return jsonify( images ), 200

@app.route('/api/status', methods=['GET'])
def status():
    return "\n ".join(processed_files)

@app.route("/api/categorize", methods=['POST'])
def categorize():
    # Decode the bytes-like object to a string
    directory_path = request.form['dPath']
    if thread_locked:
        return "processing still running"

    if not directory_path:
        return "No directory selected."

    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        return "Directory does not exist."

    thread = threading.Thread(target=file_generator, args=(directory_path,))
    thread.daemon = True
    thread.start()

    return "processing ..."


@app.route("/", methods=['GET'])
def index():
    with open("frontend/index.html", "r") as file:
        content = file.read()
    return content

if __name__ == "__main__":
    chroma_client = chromadb.PersistentClient(chroma_path)
    setup_sqlite()
    app.run(host="127.0.0.1", port="9706")