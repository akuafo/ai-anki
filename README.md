# AI-Anki Sentence Generator

This project was developed for users of Anki flashcards who want to use AI to generate sentences that assist with card memorization.  The script interacts with a locally installed Anki DB and OpenAI APIs to generate sentences and voice mp3 files and writes the output to an html file.  This was originally designed for my own learning deck for the Japanese language but should work with most Anki decks.

Pre-requisites:
* Python.
* The Anki client app installed locally on the computer where you will run the script.
* Before you start, create a backup of Anki.
* Modify the variables at the top of the script with your Anki sqlite database path, OpenAI credentials, etc.
* Install dependencies of the script.

Each time you want to run this script, you need to update the Anki app on your desktop.  This is necessary because Anki doesn't have an API for the Anki cloud, so we can only acces the data locally.

Steps to run the script:
  * Open the Anki app.
  * Click the button to synchronize the client with Anki cloud so it has the latest updates.  
  * Quit the Anki app (so database doesn't lock)
* Type the following from the console:  python main.py

This script will go through the following steps:
  * Makes a backup copy of anki database and saves in a subdirectory.
  * Queries the database for cards due on the current day
  * Uses OpenAI chat completion API to generate sentence variations
  * Uses OpenAI text to speech API to generate mp3 files
  * Writes the sentences and mp3 file links to an HTML file

Technical notes:
* Anki does not provide a cloud-based API so syncing using the Anki client on the desktop is required.  There is a feature called Anki Connect which does include an API, but it's similarly restricted to connecting locally on the desktop too and moreover requires installing an extension.  It didn't appear to offer any benefit over directly querying the sqlite database.
* The Anki sqlite database is lightly documented and card data is loosely structured.  So queries can be tricky to figure out.
* This script supports two scenarios:  vocabulary in a single language, and vocabulary for language learning.  The difference is that language learning version returns two sentences in different languages, while the single language version returns two different sentences in the same language.
This script automatically creates a backup db file each time it's run.  The file is named with a date stamp for that day so it overwrites if you run the script multiple times per day, but persists the last file that is written that day.
* OpenAI responses are fairly consistent, but do not always follow prompt instructions.  Sometimes it will generate sentences with mistakes or incorrectly convert the sentence to speech.

Roadmap:
* Update existing Anki cards by inserting the generated sentences and audio files to the original card using the note ID field.  This is challenging due to Anki flexible card template and x1 divider scheme.  One idea is to use OpenAI to analyze the template and card and figure out where to insert.
* Include new Anki cards as well as review cards
* Switch to another text-to-speech provider with a more natural Japanese voice, maybe PlayHT.
* Sort cards by hardest cards as measured by the ease value, and display the ease value in the html.
* Implement Python audio packages pydub and ffmpeg so that you can add pauses to the audio, slow it down or speed it up, and assemble multiple clips into longer podcast-style narrative audio.
* Generate conversations and role play scenarios, using vocabulary words from several different cards.
* Create a self-evaluation feedback loop for GPT-4 to assess the quality of each sentence and audio file and redo any mistakes.
* Add prompting so the user can set the technical level (intermediate, advanced, etc) for sentence generation.
* Mac:  Automation to open the Anki app and sync it and then run the script.
* Remind the user if they run the script without syncing anki first (look for recent timestamp in revlog table).
* Explore hacking Anki's desktop and mobile clients HTTP interfaces so that local app syncing is no longer necessary.
* Set maximum directory size for backups and delete older files.
* Move html/css/javascript to a python templating engine.
* Allow modification of database query to filter by custom time ranges and card difficulty levels
