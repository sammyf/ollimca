#!/bin/python
import base64

import ollama
from flask import Flask, request, send_file, jsonify, render_template, send_from_directory
from flask_cors import CORS
import threading
import requests
from pathlib import Path
from pydantic import BaseModel
import json
import os
import re

app = Flask(__name__)
CORS(app)

global thread_locked, processed_files, embed_model, vector_db_path, temperature, vision_model

processed_files = []
vision_model = "llama3.2-vision:latest"
embed_model = ""
vector_db_path = ""
temperature = 0.5
thread_locked = False

class ImageDescription(BaseModel):
    content: str
    name: str
    intent: str
    overall_color_scheme: str

def base64_encode_image(image_path):
    try:
        with open(image_path, "rb") as file:
            content = file.read()
        return base64.b64encode(content).decode('utf-8')
    except FileNotFoundError:
        return ""

def describe_image(image_path):
    b64_image = base64_encode_image(image_path)
    # Define the parameters as a dictionary
    data = {
        "model": vision_model,
        "prompt": "Tell me the following about this image : content, mood, intent, overall color scheme",
        "system": "you are a professional categorizer of image. You look at images and extract content, mood, intent and overall color scheme of the image.",
        "options": {
            "temperature": temperature,
            "keep_alive": -1
        },
        "stream": False,
        "format": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "mood": {"type": "string"},
                "intent": {"type": "string"},
                "overall_color_scheme": {"type": "string"}
            },
            "required": ["content", "mood", "intent", "overall_color_scheme"]
        },
        "images": [b64_image]
    }

    # Send a POST request to the specified URL with JSON data
    response = requests.post("http://localhost:11434/api/generate", json=data)

    # Check if the request was successful and print the response
    if response.status_code == 200:
        answer = response.json()["response"]
    else:
        answer = {"error": "Request failed with status code {}".format(response.status_code)}

    return answer

def file_generator(directory_path):
        thread_locked = True
        pattern = re.compile(r'.*.(jpg|jpeg|png|bmp)$', re.IGNORECASE)
        try:
            for root, _, files in os.walk(directory_path):
                for file in files:
                    if pattern.match(file):
                        print("Processing file: " + os.path.join(root, file))
                        print(describe_image(os.path.join(root, file)))
                        processed_files.append(os.path.join(root, file))
        except Exception as e:
            thread_locked = False
            print(f"Error processing directory: {str(e)}\n")
        thread_locked = False

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
    with open("index.html", "r") as file:
        content = file.read()
    return content

if __name__ == "__main__":
    app.run(host="127.0.0.1", port="9706")