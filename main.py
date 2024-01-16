# main.py - A python script for generating sentences and audio from Anki flashcards using the OpenAI API

import sqlite3
import datetime
import subprocess
import json
from openai import OpenAI
from pydantic import BaseModel
import re
import os
import traceback

### SET THE FOLLOWING VARIABLES BEFORE RUNNING THE SCRIPT ###

# Indicate if the Anki cards for Japanese Language (True) or not (False) to customize the openai prompt and text formatting
japanese_language = False # any anki deck
# japanese_language = True # japanese language decks

# Enter your OpenAI API key (set as an environment variable in the console so it's not hardcoded)
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)
gpt_version = 'gpt-4' # GPT version for openai
tts_version = 'tts-1' # text to speech version for openai
tts_voice = 'alloy'  # voice for text to speech for openai

# Set the location for where your Anki database is stored.  The default below is the Anki file path on Mac.  To find it on your system, search for an Anki file named 'collection.anki2'.
anki_db_path = os.path.join(os.path.expanduser("~"), "Library/Application Support/Anki2/User 1/collection.anki2")

# Set the location to store the output for the html page and audio files.   Default path is the current working directory of the script.
generated_files_path = os.path.join(os.getcwd(), "generated_files") # Use the current working directory of this script
# generated_files_path = os.path.join(os.path.expanduser("~"), "Library/Mobile Documents/com~apple~CloudDocs/AI-audiofiles/generated_files") # Use a hard-coded path in iCloud

# Filter by deck ID
deck_ids = []  # Use an empty set [] to retrieve all decks
# deck_ids = [1656891776298, 1656891776302, 1656891776303]  # Use a list of deck IDs to filter by (in Anki this is stored in the 'did' field of the cards table)  deck_ids = [1705383475022]

############

# This variable holds the html file that will be written at the end of the script
sentences_html = "<html><head><title>Generated Sentences</title><meta charset=UTF-8>"
sentences_html += """
        <style>
            table {
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
            }
            th {
                padding: 10px;
                width: 25%;
                text-align: left;
            }
            td {
                padding: 10px;
                border: 1px solid black;
                width: 25%;
                text-align: left;
                height: 50px;
                cursor: pointer; /* for click to view */
            }
            .hidden-content {
                opacity: 0.05; 
                cursor: pointer; /* for click to view */
            }

        </style>
    </head>
    <body>
"""
sentences_html += """
    <script>
    // javascript for optional click to view
    document.addEventListener('DOMContentLoaded', (event) => {
        document.querySelectorAll('.clickable').forEach(function(cell) {
            cell.addEventListener('click', function() {
                toggleVisibility(this);
            });
        });
    });
    function toggleVisibility(td) {
        var isHidden = window.getComputedStyle(td).opacity < 1;       
        if (isHidden) {
            td.style.opacity = '1';
            td.style.border = '1px solid black';
        } else {
            td.style.opacity = '0';
            td.style.border = '1px solid black'; 
        }
    }
    </script>
"""

# Function to retrieve the Anki cards from the database
def get_anki_cards():
    global sentences_html

    # Create backup of Anki in a subdirectory, this runs each time the script is run (empty your backup folder periodically)
    destination_path = "./backup"  # Location for backup files of Anki database
    print(f"\nAnki sqlite database file location:  {anki_db_path}")
    if not os.path.exists(destination_path):
        os.makedirs(destination_path)
    subprocess.run(["cp", anki_db_path, f"{destination_path}/backup_{datetime.datetime.now().strftime('%Y%m%d')}.anki2"])
    print(f"Database backup written to:  {anki_db_path}/{destination_path}/backup_{datetime.datetime.now().strftime('%Y%m%d')}.anki2\n")

    # Connect to the Anki SQLite database
    conn_anki = sqlite3.connect(anki_db_path)
    conn_anki.execute("PRAGMA journal_mode=DELETE") # this means the journal is stored in a separate file and deleted at transaction end

    # Print details of anki state for troubleshooting
    print(f"The current system time is: {datetime.datetime.now()}")
    current_unixepoch = int(conn_anki.execute('SELECT strftime(\'%s\', \'now\')').fetchone()[0])
    print(f"The current anki database time is: {datetime.datetime.fromtimestamp(int(current_unixepoch))}")

    # Start to build the table of sentences in the html file
    sentences_html += "<h1>Generated Sentences</h1>"
    sentences_html +=  f"<h2> {datetime.datetime.fromtimestamp(int(current_unixepoch))} </h2>"
    sentences_html +=  "<table>"
    if japanese_language:
        sentences_html +=  "<tr><th>Japanese</th><th>English (click to display)</th><th>Audio</th></tr>"
    else:
        sentences_html +=  "<tr><th>Sentence 1</th><th>Sentence 2</th><th>Audio</th></tr>"

    # Build SQL query to retrieve due cards
    one_day = 86400  # unix epoch time
    crt = conn_anki.execute('select crt from col').fetchone()[0]  # get the creation time of the Anki collection
    seconds_diff = current_unixepoch - crt  # calculate the number of seconds between the current time and the collection creation time
    current_day = seconds_diff // one_day  # convert the number of seconds to days
    print(f"The Anki collection was created on {datetime.datetime.fromtimestamp(int(crt))} with Anki crt of {crt}.  Therefore, today is {current_day} days after the creation date.")

    # Build SQL clause to filter by deck ID
    if deck_ids:
        deck_ids_str = str(tuple(deck_ids)) if len(deck_ids) > 1 else f"({deck_ids[0]})"
        filter_by_deck = f"c.did IN {deck_ids_str} AND "
    else:
        filter_by_deck = ""

    # Construct the SQL query to retrieve today's review cards from Anki's SQLite database
    # Note on new cards:  This query only includes review cards.  If you want to include new cards you can query with queue = 0 and omitting the time range value for new cards because anki uses the due column differently for new and review cards.
    # Note on card difficulty:  You can include card difficulty by adding 'r.ease' and 'JOIN revlog r ON c.id = r.cid' to the query
    query = f"""
    SELECT c.id, n.flds
    FROM cards c
    JOIN notes n ON c.nid = n.id 
    WHERE {filter_by_deck}due = '{current_day}'
    """

    print(query);
    print(f"\nNumber of rows in the query result: {len(conn_anki.execute(query).fetchall())}\n")

    # if no rows are returned from the database, exit the script
    if len(conn_anki.execute(query).fetchall()) == 0:
        print("No rows were returned from the Anki database.  Either you have no review cards due today, or there is a problem with the query.  Query problems could include the wrong deck IDs, a problem with the system time, or an Anki configuration that's not supported by this script.\nExiting the script.\n")
        exit()

    # iterate through the rows of the query result and call the next function to generate the sentence
    row_number = 0
    for row in conn_anki.execute(query):
        row_number = row_number + 1
        print(f"Row number: {row_number}")
        print(f"{row}\n")
        generate_sentence(row)
        # break  # UNCOMMENT TO TEST A SINGLE ROW RESULT FROM THE DATABASE

    # close the html page and write to file 'generated_sentences.html'
    sentences_html += "</table></body></html>"
    subfolder_path = generated_files_path + "/" + datetime.datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(subfolder_path, "sentences-web-page.html")
    if not os.path.exists(subfolder_path):
        os.makedirs(subfolder_path)
    f = open(file_path, "w", encoding='utf-8')
    f.write(sentences_html)
    f.close()
    print("Sentences HTML file saved to the following location:")
    print(os.path.join(file_path.replace(" ", "%20")))
    print("\n")

# Function to generate the sentence using the OpenAI chat completion API
def generate_sentence(item):

    # You can modify the prompt below according to your Anki flashcard use case.
    if japanese_language:
        prompt_messages = [
            {
                "role": "system",
                "content": "You will be given an Anki note from a flashcard deck.   You will respond with JSON with three items of sentence1, sentence2, and id.  sentence1 is a string of Japanese text consisting of a generated sentence that will help give context to the person learning the flashcards (NOTE:  ALL KANJI IN THE JAPANESE MUST BE ENCLOSED WITH HTML RUBY TAGS WITH FURIGANA IN RT TAGS). sentence2 is a string of English text and consists of an English translation of sentence1.  id is the ID of the Anki note.  THE JSON MUST ALWAYS USE DOUBLE QUOTES.  Here is example JSON: {\"sentence1\": \"<ruby>老人<rt>ろうじん</rt></ruby><ruby>施設<rt>しせつ</rt></ruby>で<ruby>働<rt>はたら</rt></ruby>くことは、<ruby>多<rt>おお</rt></ruby>くの<ruby>人<rt>ひと</rt></ruby>にとって<ruby>非常<rt>ひじょう</rt></ruby>にやりがいのある<ruby>経験<rt>けいけん</rt></ruby>です。\", \"sentence2\": \"Working in an elderly care facility is a very rewarding experience for many people.\", \"id\": 1671244560415}"
            },
            {
                "role": "user",
                "content": json.dumps(item, ensure_ascii=False)
            }
        ]
    else:
        prompt_messages =  [
            {
              "role": "system",
                "content": "You will be given an Anki note from a flashcard deck.   You will respond with JSON with three items of sentence1, sentence2, and id.  sentence1 and sentence2 are generated sentences that use the word in context.  id is the ID of the Anki note.  THE JSON MUST ALWAYS USE DOUBLE QUOTES.  Here is example JSON: {\"sentence1\": \"A rare parathyroid disease and phosphocalcic metabolism anomaly characterized by hypocalcemia, hyperphosphatemia, hypercalciuria, and low serum parathyroid hormone levels, in the presence of autoantibodies against parathyroid tissue.\", \"sentence2\": \"Hypoparathyroidism, a disorder characterized by inadequate parathyroid hormone production, typically presents with symptoms such as muscle cramps, tetany, and circumoral numbness due to hypocalcemia.\", \"id\": 1671244560415}"
            },
            {
                "role": "user",
                "content": json.dumps(item, ensure_ascii=False)
            }
        ]
    # prompt_messages = [{"role": "system", "content": "you are an academic pirate."}, {"role": "user", "content": "what is the value of pi?"}]  # TEST A BAD OPENAI RESPONSE

    # Build the openai message array
    messages_generate = []
    messages_generate.append(prompt_messages[0])
    messages_generate.append(prompt_messages[1])

    try:
        # Call the OpenAI API with the python sdk
        chat_response = client.chat.completions.create(
            messages=messages_generate,
            model=gpt_version,
        )

        # Convert the JSON response to a python dictionary
        response_dict = json.loads(chat_response.choices[0].message.content)

        # Define a Pydantic model and validate the response data
        class SentenceResponse(BaseModel):
            sentence1: str
            sentence2: str
            id: int
        parsed_response = SentenceResponse(**response_dict)

        print("OpenAI chat completion response")

        # Call the next function for the text to speech API
        text_to_speech(parsed_response)

    except Exception as e:
        print("\nError occurred with OpenAI chat completion API...\n")
        print(f"\nAPI response: {chat_response}\n") if 'chat_response' in locals() else None
        traceback.print_exc()
        print("\nExiting the script.\n")
        exit()

# Function to generate the audio as mp3 files using the OpenAI text to speech API
def text_to_speech(sentences):
    global sentences_html

    print(sentences.sentence1 + " [pause] " + sentences.sentence2)

    try:
        # Use the python SDK to call the OpenAI text to speech API, and strip html tags
        response = client.audio.speech.create(
            model=tts_version, 
            voice=tts_voice, 
            input=re.sub(r'<ruby>(.*?)<rt>(.*?)</rt></ruby>', r'\1', sentences.sentence1) + " [pause] " + sentences.sentence2
        )
    except Exception as e:
        print(f"\nAn error occurred with the text to speech api: {e}")
        print(f"\nAPI response: {response}\n") if 'response' in locals() else None
        traceback.print_exc()
        print("\nExiting the script.\n")
        exit()

    # Save the generated speech as an mp3 file in the subfolder       
    subfolder_path = os.path.join(generated_files_path, datetime.datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(subfolder_path, exist_ok=True)
    file_path = os.path.join(subfolder_path, f"speech-{sentences.id}.mp3")
    response.stream_to_file(file_path)
    print(f"Saved file: {file_path}\n")

    # Build the HTML table row for the sentence
    sentences_html += "<tr>"
    # if japanese, use furigana and 'click to reveal' the sentence.  for all others, build regular html with just sentences.
    if japanese_language:
        sentences_html += "<td>" + sentences.sentence1
        # uncomment the following line if you want to display sentences with 1. Kanji only, 2. Anki furigana separator []
        # sentences_html += "<br>kanji only:  " + re.sub(r'<ruby>(.*?)<rt>(.*?)</rt></ruby>', r'\1', sentences.sentence1) + "<br>anki format:" + re.sub(r'<rt>(.*?)</rt>', r'[\1]', sentences.sentence1)
        sentences_html += "</td>"
        sentences_html += "<td class=\"clickable hidden-content\">" + sentences.sentence2 + "</td>" # 'click to reveal' for language learning
    else:
        sentences_html += "<td>" + sentences.sentence1 + "</td>"
        sentences_html += "<td>" + sentences.sentence2 + "</td>"
    sentences_html += "<td><audio controls><source src=\"" + f"speech-{sentences.id}.mp3" + "\" type=\"audio/mpeg\">The html audio element is not supported.</audio></td>"
    sentences_html += "</tr>"

# call the first function
get_anki_cards() 
