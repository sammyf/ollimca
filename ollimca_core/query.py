import ollama
import json
import chromadb
import os
import re
import sqlite3

class Query:
    def __init__(self, sqlite_path, chroma_path, embedding_model):
        self.chroma_path = chroma_path
        self.sqlite_path = sqlite_path
        self.embedding_model = embedding_model
        self.chroma_client = chromadb.PersistentClient(chroma_path)

    def query(self, content, mood, colors, page_sql, page_chroma, items_per_page):
        images=[]
        if content.strip() != '':
            images = self.query_sqlite(content, page_sql, items_per_page)
            page_sql +=1
        if len(images) <= items_per_page:
            chroma_rs=self.query_chroma(content, mood, colors, page_chroma, items_per_page)
            images.extend(chroma_rs)
            page_chroma += 1
        return (images, page_sql, page_chroma)

    def query_sqlite(self, content, page, items_per_page):
        rs=[]
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute('SELECT path FROM images WHERE content LIKE ? LIMIT ?, ?', ('%' + content + '%', page*items_per_page, items_per_page))
        paths = cursor.fetchall()
        rs = [row[0] for row in paths]
        conn.close()
        return rs

    def query_chroma(self, content, mood, colors, page, items_per_page):
        search_query = ""
        if content.strip() != "":
            search_query += "description:" + content
        if mood.strip() != "":
            search_query += "\nmood: " + mood
        if colors.strip() != "":
            search_query += "\noverall_color_scheme: " + colors

        response = ollama.embeddings(
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
            cutoff = items_per_page * (page - 1)
            if cutoff > 0:
                documents = results["documents"][0][cutoff:]
            else:
                documents = results["documents"][0]
            for document in documents:
                images.append(document)
        return images

