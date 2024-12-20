# OLLIMCA (OLLama IMage CAtaloguiser)

(Licensed under GPLv3. See the LICENSE file for details.)

This small tool crawls through all the images in directories and their subdirectories and sends 
them to a LLM with vision running on a local instance of 'ollama' ( https://ollama.com )
The LLM then writes a description of the image which is stored in a database. 

You can then use the provided stand-alone frontend to search for images featuring the keywords you enter.

### installation :

You will need python3 with venv installed. 

On Linux:
Run ./install.sh

update config.yaml with the relevant data. The chromadb and sqlite paths are just the name of the files created. 
They will be located in the 'db' directory. 

The default models should work even for people without GPU, but it will
still be slow. Also : while moondream is a great and very small vision model *most of the time*, it has a small bug 
which makes it fail on some images.

Do not forget to set an image viewer that should be started when an image is clicked.  (/usr/bin/gwenview if you are
using KDE for example)

### installation :

Run ./start_server.sh to start the crawler webserver 
Open http://localhost:9706  to open the crawler's page. Enter a directory with images in it, press
the button ... and wait. Like seriously ... On my system (i7-10700k, 64GB RAM, RTX3090/24GB) the program crawls through
approximately 1200 images per hour. Depending on the amount of image files, you might be looking for weeks to get through
everything. Luckily you can stop the process anytime and continue later on.

Also : please note that only jpg, jpeg and png files are looked at (the case is irrelevant, jpg and JPG work!)

You can then use the frontend ( started with python search.py if it didn't open automatically) to search the files that were 
analyzed so far. The frontend is standalone. Thankfully, the search itself is very fast. 
It's important to understand that the search is only vector based for now, which means that
queries are semantic and will ALWAYS return something, even if the terms you entered are not found 'literally'. Searching 
for, for example, 'pinguin' will return pictures of pinguins, but also of other birds, the sea, possibly fish and ice too.

This is a work in progress,so expect bugs, weird happenstances and missing features you just don't get why I didn't 
implement them yet ... ¯\_(ツ)_/¯


Heads up to the nice folks on the ollama Discord Server for their cheering and verbal abuse.

<a href="https://www.buymeacoffee.com/socialnetwooky" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

![](screenshots/creepy.png)

