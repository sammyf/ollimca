#!/bin/python
import base64
import json
from sqlite3 import sqlite_version
from ollimca_core.query import Query
from ollimca_core.config import Config
from flask import Response

from ollama import Client as OllamaClient

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

global ollama_client, ollama_embed_client, chroma_path, thread_locked, processed_files, embedding_model, vector_db_path, sqlite_path,  temperature, vision_model, chroma_client

vision_model = "moondream:latest"
embedding_model = "nomic-embed-text:latest"
temperature = 1.31
ollama_crawl = "127.0.0.1:11434"
ollama_embed = "127.0.0.1:11434"
host = "127.0.0.1"
port = "9706"

ollama_client = None
ollama_embed_client = None
chroma_path = os.path.join("db","ollimca_chroma.db")
sqlite_path = os.path.join("db","ollimca_sqlite3.db")
processed_files = []
thread_locked = False
chroma_client = None

class ImageDescription(BaseModel):
    description: str
    mood: str
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
    fulltext="description: "+description.description+"\nmood: "+description.mood+"\ncolor_scheme: "+description.overall_color_scheme
    print(fulltext)
    description_as_dict = {
        "description":description.description,
        "mood":description.mood,
        "color_scheme":description.overall_color_scheme
    }
    collection = chroma_client.get_or_create_collection('images')

    response = ollama_embed_client.embeddings(model=embedding_model, prompt=fulltext, keep_alive=-1, options={ temperature:0})
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

def complex_image_query(image_path):
    response = ollama_client.chat (
        model=vision_model,
        messages=[
            {
                'role': 'user',
                'content': 'describe the content of that image. What can be seen? If there is text visible, what does it say? use detailed keywords!',
                'images': [image_path],
            },
        ],
        options={
            'temperature': temperature,
            'keep_alive': -1
        },
        stream=False,
    )
    description = response.message.content

    return description

def simple_image_query(image_path):
    response = ollama_client.chat (
        model=vision_model,
        format=ImageDescription.model_json_schema(),  # Pass in the schema for the response
        messages=[
            {
                'role': 'user',
                'content': 'Tell me the following about this image, be as detailed as possible: description, mood, color names of the overall color scheme.',
                'images': [image_path],
            },
        ],
        options={
            'temperature': temperature,
            'keep_alive': -1
        },
        stream=False,
    )
    return ImageDescription.model_validate_json(response.message.content)

def describe_and_store_image(str_image_path,dbid, complex):
    image_path = Path(str_image_path)

    answer=simple_image_query(image_path)

    if complex == 1:
        description = complex_image_query(image_path)
        answer.description = description

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

def file_generator(directory_path, complex):
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
                            content = describe_and_store_image(file_path, dbid, complex)
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
    query = Query(chroma_path, embedding_model)
    return Response(query.Query(content, mood, colors, page, items_per_page), mimetype='application/json'), 200


@app.route('/api/status', methods=['GET'])
def status():
    return "\n ".join(processed_files)

@app.route("/api/categorize", methods=['POST'])
def categorize():
    complex = 0
    # Decode the bytes-like object to a string
    directory_path = request.form['dPath']
    if "complex" in request.form:
        complex = 1
    if thread_locked:
        return "processing still running"

    if not directory_path:
        return "No directory selected."

    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        return "Directory does not exist."

    thread = threading.Thread(target=file_generator, args=(directory_path,complex))
    thread.daemon = True
    thread.start()

    return "processing ..."


@app.route("/", methods=['GET'])
def index():
    with open("frontend/index.html", "r") as file:
        content = file.read()
    return content

if __name__ == "__main__":
    cfg = Config()
    config = cfg.ReadConfig()
    vision_model = config["vision_model"]
    embedding_model = config["embedding_model"]
    temperature = config["temperature"]

    chroma_path = os.path.join("db", config['db']['chroma_path'])
    sqlite_path = os.path.join("db", config['db']['sqlite_path'])

    ollama_crawl = config["ollama_crawl"]
    ollama_embed = config["ollama_embed"]
    flask_host = config["host"]
    flask_port = config["port"]

    ollama_client = OllamaClient(
        host=ollama_crawl
    )

    ollama_embed_client = OllamaClient(
        host=ollama_embed
    )

    chroma_client = chromadb.PersistentClient(chroma_path)

    setup_sqlite()
    app.run(flask_host, flask_port)