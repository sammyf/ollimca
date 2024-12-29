from ollama import Client as OllamaClient
import json
import chromadb
import os
import re
import sqlite3
import hashlib

class Query:
    def __init__(self, sqlite_path, chroma_path, embedding_model, ollama_embed):
        self.chroma_path = chroma_path
        self.sqlite_path = sqlite_path
        self.embedding_model = embedding_model
        self.chroma_client = chromadb.PersistentClient(chroma_path)
        self.already_shown_images=[]
        self.checksums=[]
        self.sha256_hash = hashlib.sha256()
        self.delete_duplicate_missing = False
        self.ollama_embed_client = OllamaClient(
            host=ollama_embed
        )

    def query(self, content, mood, colors, page_sql, page_chroma, items_per_page, already_shown_images, checksums, delete_duplicates_missing):
        images=[]
        self.checksums = checksums
        self.already_shown_images = already_shown_images
        self.delete_duplicate_missing = delete_duplicates_missing
        if content.strip() != '':
            images = self.query_sqlite(content, page_sql, items_per_page)
            page_sql +=1
        if len(images) <= items_per_page:
            chroma_rs=self.query_chroma(content, mood, colors, page_chroma, items_per_page)
            images.extend(chroma_rs)
            page_chroma += 1
        return (images, page_sql, page_chroma,self.already_shown_images, self.checksums)

    def query_sqlite(self, content, page, items_per_page):
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, path, content FROM images WHERE content LIKE ? OR path LIKE ? ORDER BY id LIMIT ?, ?', ('% ' + content + ' %', '% ' + content + ' %', page*items_per_page, items_per_page))
        paths = cursor.fetchall()
        rs = []
        for row in paths:
            if self.check_duplicate(row[1], row[0]):
                continue
            if row[1] in self.already_shown_images:
                continue
            self.already_shown_images.append(row[1])
            rs.append([row[1],row[2]])
        conn.close()
        return rs

    def query_chroma(self, content, mood, colors, page, items_per_page):
        search_query = ""
        if content.strip() != "":
            search_query += "\"\"an image showing " + content+"\"\""
        if mood.strip() != "":
            search_query += "\n\"\"the overall mood conveyed by the image is " + mood+"\"\""
        if colors.strip() != "":
            search_query += "\n\"\"the overall color scheme of this image is " + colors+"\"\""

        response = self.ollama_embed_client.embeddings(
            prompt=search_query,
            model=self.embedding_model,
            keep_alive=-1
        )
        collection = self.chroma_client.get_or_create_collection(name='images')
        results = collection.query(
            query_embeddings=[response['embedding']],
            n_results=(page * items_per_page),
        )
        images = []
        if len(results) > 0:
            selected_images = 0
            documents = results["documents"][0]
            ids = results["ids"][0]
            content = results["metadatas"][0]
            for document, image_id, meta in zip(documents, ids, content):
                if self.check_duplicate(document, image_id):
                    continue
                if document in self.already_shown_images:
                    continue
                self.already_shown_images.append(document)
                images.append([document,meta["description"]])
                selected_images += 1
                if selected_images >= items_per_page:
                    break
        return images

    def check_duplicate(self,image_path, image_id):
        if self.delete_duplicate_missing:
            checksum = self.get_sha256_checksum(image_path)
            if (checksum == "...") or (checksum in self.checksums):
                if os.path.exists(image_path):
                    print(f"removing {image_path}")
                    self.remove_image(image_id)
                    # ²
                return True
            else:
                self.checksums.append(checksum)
        return False


    def remove_image(self,image_id):
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
        conn.commit()
        conn.close()

        collection = self.chroma_client.get_or_create_collection(name='images')
        entry_id = str(image_id)
        collection.delete(ids=[entry_id])

    def get_sha256_checksum(self, file_path):

        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    self.sha256_hash.update(byte_block)
            return self.sha256_hash.hexdigest()
        except:
            return "..."
