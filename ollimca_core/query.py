import ollama
import json
import chromadb
import os
import re


class Query:
    def __init__(self, chroma_path, embedding_model):
        self.chroma_path = chroma_path
        self.embedding_model = embedding_model
        self.chroma_client = chromadb.PersistentClient(chroma_path)

    def Query(self, content, mood, colors, page, items_per_page):
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

