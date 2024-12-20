import os
import yaml


class Config:
    def __init__(self):
        pass

    def ReadConfig(self):
        # Read the YAML file
        with open('config.yaml', 'r') as file:
            config = yaml.safe_load(file)

        return config