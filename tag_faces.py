#!/bin/bash
from ctypes.wintypes import tagMSG

import face_recognition
import face_recognition_models
import sqlite3
from ollimca_core.config import Config
import os
import glob
from PIL import Image
import numpy as np


def scale_image(input_path, max_size=2000):
    # Open an image file
    with Image.open(input_path) as img:
        # Get original dimensions
        width, height = img.size

        # Calculate the scaling factor
        if width > height:
            scale_factor = max_size / width
        else:
            scale_factor = max_size / height

        # Calculate new dimensions
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)

        # Resize the image
        resized_img = img.resize((new_width, new_height), Image.FILTERED)
        return np.array(resized_img)


class TagFaces:
    known_faces = []
    def __init__(self):
        cfg = Config()
        config = cfg.ReadConfig()
        self.sqlite_path = os.path.join("db", config['db']['sqlite_path'])
        known_faces_path=glob.glob("faces/*.jpg")
        for face in known_faces_path:
            callname = os.path.basename(face).replace('.jpg','')
            id = self.find_or_create_id(face)
            img = face_recognition.load_image_file(face)
            self.known_faces.append([str(id), callname,face_recognition.face_encodings(img, model="cnn")[0]])

    def find_or_create_id(self, callname):
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM persons WHERE callname=?',(callname,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            id = row[0]
        else:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO persons (callname) VALUES (?)',(callname,))
            id = cursor.lastrowid

        conn.close()
        return id

    def add_tag_to_db(self):
        conn = sqlite3.connect(self.sqlite_path)

        cursor = conn.cursor()
        cursor.execute('SELECT id, path, persons_ids FROM images')
        rows = cursor.fetchall()
        cursor.close()
        rs = []
        for row in rows:
            print(f"processing {row[1]}")
            try:
                    # Load image and detect faces
                    #img = face_recognition.load_image_file(row[1],scale=True)
                    img = scale_image(row[1])
                    face_locations = face_recognition.face_locations(img)
                    if len(face_locations) == 0:
                        continue

                    # Verify face identity
                    recognized_faces = ";".split(row[2])
                    for face in self.known_faces:
                        if face[0] in recognized_faces:
                            continue
                        # print(f"\tcomparing to {face[1]}")
                        rs=self.test(img,face[2])
                        if rs:
                            recognized_faces.append(face[0])
                            print(f"Faces match: {face[1]} is in {row[1]}!")

                    if len(recognized_faces) > 0:
                        cursor = conn.cursor()
                        cursor.execute('UPDATE images SET persons_ids=? WHERE id=?', (';'.join(recognized_faces),row[0],))
                        cursor.close()
            except:
                print(row[1]+" could not be recognized")
        conn.close()


    def test(self,img, face):
        # my_face_encoding now contains a universal 'encoding' of my facial features that can be compared to any other picture of a face!
        unknown_face_encoding = face_recognition.face_encodings(img, model="cnn")[0]
        # Now we can see the two face encodings are of the same person with `compare_faces`!
        results = face_recognition.compare_faces([face], unknown_face_encoding, tolerance=0.5)
        return results[0]

if __name__ == "__main__":
    tagger = TagFaces()
    tagger.add_tag_to_db()
