#!/bin/bash
from ctypes.wintypes import tagMSG

import face_recognition
import sqlite3
from ollimca_core import config
import os
import glob

class TagFaces:
    def __init__(self):
        self.cfg = config.Config()
        self.sqlite_path = os.path.join("db", config['db']['sqlite_path'])
        self.known_faces=glob.glob("faces/*.png")

    def add_tag_to_db(self):
        conn = sqlite3.connect(self.sqlite_path)

        cursor = conn.cursor()
        cursor.execute('SELECT id, path, content FROM images WHERE content NOT LIKE "%#?#PERSONS:%#!#"')
        rows = cursor.fetchall()
        rs = []
        for row in rows:
            # Load image and detect faces
            img = face_recognition.load_image_file(row[1])
            faces = face_recognition.face_locations(img)

            # Extract face embeddings
            embeddings = face_recognition.face_encodings(img, faces)

            # Verify face identity
            for face in self.known_faces:
                known_face = face_recognition.face_encodings('known_face.jpg')[0]
                distance = face_recognition.face_distance(embeddings[0], known_face)
                if distance < 0.6:  # threshold for verification
                    print(f"Faces match: {os.path.basename(face)} is in {row[1]}!")
        conn.close()

if __name__ == "__main__":
    tagger = TagFaces()
    tagger.add_tag_to_db()
