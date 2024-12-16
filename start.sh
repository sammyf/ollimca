#!/bin/bash
source ollivenv/bin/activate && python search.py > /dev/null &
source ollivenv/bin/activate && python ollimca.py > /dev/null
