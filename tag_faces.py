#!/bin/bash
from ctypes import c_int
from ctypes.wintypes import tagMSG

import face_recognition
import face_recognition_models
import sqlite3
from ollimca_core.config import Config
import os
import glob
from PIL import Image
import numpy as np
import torch
from facenet_pytorch import InceptionResnetV1
from torchvision import transforms
from dlib import get_frontal_face_detector, shape_predictor


class TagFaces:
    known_faces = []
    def __init__(self):
        self.model = InceptionResnetV1(pretrained='vggface2').eval()
        # Define a transformation to prepare images for the model
        self.transform = transforms.Compose([
            transforms.Resize((160, 160)),
            transforms.ToTensor()
        ])

        self.detector = get_frontal_face_detector()
        self.predictor = shape_predictor("shape_predictor_68_face_landmarks.dat")
        self.threshold = 0.5

        cfg = Config()
        config = cfg.ReadConfig()
        self.sqlite_path = os.path.join("db", config['db']['sqlite_path'])
        known_faces_path=glob.glob("faces/*.jpg")
        for face in known_faces_path:
            callname = os.path.basename(face).replace('.jpg','')
            id = self.find_or_create_id(callname)
            self.known_faces.append([str(id), callname,self.get_face_embedding(face)])

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
        conn.commit()
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

            # Verify face identity
            if row[2] != "" and row[2] != None:
                recognized_faces = ";".split(row[2])
            else:
                recognized_faces = []
            try:
                cropped_faces = self.detect_and_crop_faces(row[1])
                if len(cropped_faces) == 0:
                    continue
                for face_region in cropped_faces:
                    face_region.save("/tmp/cropped_face.jpg")
                    embed = self.get_face_embedding("/tmp/cropped_face.jpg")
                    #embed = self.get_face_embedding(row[1])
                    for face in self.known_faces:
                        if face[0] in recognized_faces:
                            continue
                        rs = self.compare_embeddings(face[2], embed)
                        if rs:
                            recognized_faces.append(face[0])
                            print(f"Faces match: {face[1]} is in {row[1]}!")
                            continue
            except Exception as e:
                print(f"Error processing image {row[1]}: {e}")
            if len(recognized_faces) > 0:
                cursor = conn.cursor()
                cursor.execute('UPDATE images SET persons_ids=? WHERE id=?', (';'+';'.join(recognized_faces)+';',row[0],))
                conn.commit()
        conn.close()

    def get_face_embedding(self, image_path):
        """
        Extracts and returns facial embeddings from an image.

        Parameters:
        - image_path: Path to the image file

        Returns:
        - embeddings: Tensor containing facial embeddings
        """
        img = Image.open(image_path).convert('RGB')
        img_tensor = self.transform(img)
        # Ensure batch dimension is added
        img_tensor = img_tensor.unsqueeze(0)

        with torch.no_grad():
            embedding = self.model(img_tensor)

        return embedding


    def compare_embeddings(self, embedding1, embedding2, threshold=0.6):
        """
        Compares two facial embeddings.

        Parameters:
        - embedding1: First facial embedding
        - embedding2: Second facial embedding
        - threshold: Similarity threshold (default: 0.6)

        Returns:
        - True if embeddings are similar enough, False otherwise
        """
        similarity = torch.nn.functional.cosine_similarity(embedding1, embedding2)
        return similarity.item() >= self.threshold


    def detect_and_crop_faces(self, image_path):
        img_raw = Image.open(image_path).convert('RGB')
        img=np.array(img_raw)

        face_locations = face_recognition.face_locations(img)
        cropped_faces = []

        for location in face_locations:
            top = location[0]
            right = location[1]
            bottom = location[2]
            left = location[3]
            face_region = img_raw.crop((left, top, right, bottom))
            cropped_faces.append(face_region)
        return cropped_faces

if __name__ == "__main__":
    tagger = TagFaces()
    tagger.add_tag_to_db()
