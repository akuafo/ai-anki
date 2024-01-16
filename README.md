# AI-Anki Sentence Generator

This project was developed for users of Anki flashcards who want to use AI to generate sentences that assist with card memorization.  The script interacts with a locally installed Anki DB and OpenAI APIs to generate sentences and voice mp3 files and writes the output to an html file.  This was originally designed for my own learning deck for the Japanese language but should work with most Anki decks.

Pre-requisites:
* Python
* The Anki client app needs to be installed on the computer where you will run the script (see below for more info)

Setup:
* Install Python packages:  
`pip install -r requirements.txt`
* Modify the variables at the top of the script main.py for the database path, OpenAI credentials, etc.
Run the script:
* Create a backup of Anki (the script will also make a backup before it runs)
* Open the Anki desktop app
* Click the button to synchronize, so it gets your latest updates from Anki
* Quit the Anki app, so the database doesn't lock
* Run the script:  
`python main.py`

The script will do the following actions:
Make a backup copy of anki database and save in a subdirectory
Query the database for the review cards that are due on the current day
Request to the OpenAI chat completion API to generate sentence variations
Request to the OpenAI text to speech API to generate mp3 files
Write the sentences and mp3 file links to an HTML file

Some technical notes:
Anki does not provide a cloud-based API so installing the Anki client on the desktop is the only practical way to access an Anki deck.  There is a feature called Anki Connect which does include an API, but it's similarly restricted to only local connections from the desktop.  Moreover, it requires installing an extension.  So there didn't appear to offer any benefit of using Anki Connect over directly querying the sqlite database.
This script supports two scenarios:  vocabulary in a single language, and vocabulary for language learning.  The difference is that language learning version returns two sentences in different languages, while the single language version returns two different sentences in the same language.  They use different OpenAI prompts which can be customized.
Currently only review cards are supported.
This script automatically creates a backup db file each time it's run.  The file is named with a date stamp for that day so it overwrites if you run the script multiple times per day, but persists the last file that is written that day.
OpenAI responses are fairly consistent, but do not always follow prompt instructions.  Sometimes it will generate sentences with mistakes or incorrectly convert the sentence to speech.

Ideas for roadmap (work in progress):
* Update the existing Anki cards with the generated sentences and audio files by inserting to the same note ID.  This is challenging due to Anki unstructured template-based card format and x1 divider scheme, which means it's unclear where to insert the sentences in any given Anki deck.  One idea is to use OpenAI to analyze the template and card of the deck and figure out where to insert.
* Include new Anki cards as well as review cards ('due' for new cards is different time calculation than review cards).
* Switch to another text-to-speech provider with a more natural Japanese voice, maybe PlayHT.
* Sort cards by the hardest cards first, as measured by 'ease'.
* Implement Python audio packages pydub and ffmpeg in order to add pauses to the audio, slow it down or speed it up, and assemble multiple clips into longer podcast-style narrative audio.
* Generate conversations and role play scenarios.  Mix and match vocabulary words from multiple cards.
* Create a self-evaluation feedback loop for GPT-4 to assess the quality of each sentence and audio file and redo if there are mistakes.
* Add prompting so the user can set their level (intermediate, advanced, etc) and get appropriately complex sentences.
* Reminder to the user if they forget to sync anki before running the script (based on timestamp in revlog table).
* Mac:  Automation to open the Anki app and sync it and then run the script.
* Explore hacking the Anki client app's HTTP interfaces so that the desktop app is unnecessary.
* Set maximum size for backup directory and delete older files.
* Separate out the html/css/javascript using a python templating engine.
* Allow passing of parameters to database query for custom time ranges, card difficulty levels, and other filters.
