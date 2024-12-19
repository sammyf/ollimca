import os
import yaml


class Config:
    def __init__(self):
        pass

    def ReadConfig(self):
        # Read the YAML file
        with open('config.yaml', 'r') as file:
            config = yaml.safe_load(file)

        # Extract parameters from the YAML file
        vision_model = config['vision_model']
        embedding_model = config['embedding_model']
        temperature = config['temperature']

        chroma_path = os.path.join("db", config['db']['chroma_path'])
        sqlite_path = os.path.join("db", config['db']['sqlite_path'])

        return {
            'vision_model': vision_model,
            'embedding_model': embedding_model,
            'temperature': temperature,
            'chroma_path': chroma_path,
            'sqlite_path': sqlite_path
        }