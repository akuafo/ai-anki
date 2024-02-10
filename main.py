# main.py - A python script for generating sentences and audio from Anki flashcards using OpenAI and Microsoft Azure APIs

import sqlite3
import datetime
import subprocess
import json
import re
import os
import traceback
from pydantic import BaseModel
from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk

### SET THE FOLLOWING VARIABLES BEFORE RUNNING THE SCRIPT ###

# Indicate if the Anki cards for Japanese Language (True) or not (False) to customize the openai prompt and text formatting
# japanese_language = False # any anki deck
japanese_language = True # japanese language decks

# Enter your OpenAI API key (set as an environment variable in the console so it's not hardcoded)
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)
gpt_version = 'gpt-4-1106-preview'

# Enter Microsoft Azure key (requires setting up an Azure resource with the Speech service, free tier is generous)
MICROSOFT_TTS_KEY1 = os.environ.get('MICROSOFT_TTS_KEY1')

# Set the location for where your Anki database is stored.  The default below is the Anki file path on Mac.  To find it on your system, search for an Anki file named 'collection.anki2'.
anki_db_path = os.path.join(os.path.expanduser("~"), "Library/Application Support/Anki2/User 1/collection.anki2")

# Set the location to store the output for the html page and audio files.
# generated_files_path = os.path.join(os.getcwd(), "generated_files") # Use the current working directory of this script
generated_files_path = os.path.join(os.path.expanduser("~"), "Library/Mobile Documents/com~apple~CloudDocs/AI-audiofiles/generated_files") # Use a hard-coded path in iCloud

# Filter by deck ID
# deck_ids = []  # Use an empty set [] to retrieve all decks
deck_ids = [1656891776298, 1656891776302, 1656891776303]  # Use a list of deck IDs to filter by (in Anki this is stored in the 'did' field of the cards table)  deck_ids = [1705383475022]

############

# This variable holds the html file that will be written at the end of the script
sentences_html = "<html><head><title>Generated Sentences</title><meta charset=UTF-8>"
sentences_html += """
        <style>
            table {
                width: 100%;
                border-collapse: collapse;
                table-layout: auto;
            }
            th {
                padding: 10px;
                text-align: left;
            }
            td {
                padding: 10px;
                border: 1px solid black;
                text-align: left;
                font-size: larger;
                height: 50px;
                cursor: pointer; /* for click to view */
            }
            .hidden-content {
                opacity: 0.05; 
                cursor: pointer; /* for click to view */
            }
            .small-text {
                font-size: smaller;
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
    try:
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
        # This query only includes review cards.  If you want to include new cards you can query with queue = 0 and omitting the time range value for new cards because anki uses the due column differently for new and review cards.
        query = f"""
        SELECT c.id, n.flds, r.lastIvl, r.ease, c.flags 
        FROM cards c 
        JOIN notes n ON c.nid = n.id 
        JOIN (SELECT cid, MAX(id) as max_id FROM revlog GROUP BY cid) as x ON c.id = x.cid 
        JOIN revlog r ON x.cid = r.cid AND x.max_id = r.id 
        WHERE {filter_by_deck}due = '{current_day}'
        ORDER BY c.flags DESC, r.ease ASC;
        """
        # Query response will include the following columns:
        # 0:  id - the id from cards
        # 1:  flds - the card (string of fields separated by \x1f) from notes
        # 2:  flags - flags from cards
        # 3:  ease - most recent ease value from revlogs
        # 4:  lastIvl - most recent interval value from revlogs

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
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn_anki:
            conn_anki.close()
            print("Database connection closed.")

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

    # The 'item' is a row from the Anki database as a tuple, for example:
    # anki row: (1665999186835, 'ちっとも\x1fちっとも\x1f\x1fNot at all (negative sentence)\x1f\x1f\x1fSimilar to ぜんぜん')

    # print(f"First two elements of the python object: {item[:2]}\n")
    # print(f"All elements of the python object: {item}\n")

    # You can modify the prompts below according to your Anki flashcard use case.
    if japanese_language:
        prompt_messages = [
            {
                "role": "system",
                "content": "You will be given an Anki note from a flashcard deck.   You will respond with JSON with two sentences: sentence1 and sentence2.  sentence1 is a generated sentence in Japanese that will help the person learn the flashcard.  KANJI MUST INCLUDE RUBY AND RT TAGS WITH FURIGANA, FOR EXAMPLE:  <ruby>老人<rt>ろうじん</rt></ruby>, BUT HIRAGANA AND KATAKANA SHOULD NEVER BE ENCLOSED IN RUBY TAGS.  sentence2 is a string of English text and consists of an English translation of sentence1.  THE JSON RESPONSE MUST ALWAYS USE DOUBLE QUOTES."
            },
            {
                "role": "user",
                "content": "(1440785141775, '届きます\x1f届[とど]きます/とどく\x1f[ 荷物[にもつ]が～]\x1f[parcels] be delivered\x1fI\x1f36\x1fI\x1f\x1f\x1fHint: ‘to do’<div><br></div><div>The package has arrived.</div>\x1f', 32, 2, 0)"
            },
            {
                "role": "assistant",
                "content": "<ruby>荷物<rt>にもつ</rt></ruby>が<ruby>届<rt>とど</rt></ruby>きました。 [pause] The package has arrived."
            },
            {
                "role": "user",
                "content": "(1622075780091, 'それまでに\x1fそれまでに宿題を終わらせます。\x1fI’ll finish my homework by that time.\x1f48\x1f\nそれまでに&nbsp;by that time', 98, 2, 7)"
            },
            {
                "role": "assistant",
                "content": "それまでに<ruby>宿題<rt>しゅくだい</rt></ruby>を<ruby>終<rt>お</rt></ruby>わらせます。"
            },
            {
                "role": "user",
                "content": json.dumps(item[:2], ensure_ascii=False)
            }
        ]
        messages_generate = []
        messages_generate.append(prompt_messages[0])
        messages_generate.append(prompt_messages[1])
        messages_generate.append(prompt_messages[2])
        messages_generate.append(prompt_messages[3])
        messages_generate.append(prompt_messages[4])
        messages_generate.append(prompt_messages[5])
    else:
        prompt_messages =  [
            {
              "role": "system",
                "content": "You will be given an Anki note from a flashcard deck.   You will respond with JSON with three items of sentence1, sentence2, and id.  sentence1 and sentence2 are generated sentences that use the word in context.  id is the ID of the Anki note.  THE JSON MUST ALWAYS USE DOUBLE QUOTES.  Here is example JSON: {\"sentence1\": \"A rare parathyroid disease and phosphocalcic metabolism anomaly characterized by hypocalcemia, hyperphosphatemia, hypercalciuria, and low serum parathyroid hormone levels, in the presence of autoantibodies against parathyroid tissue.\", \"sentence2\": \"Hypoparathyroidism, a disorder characterized by inadequate parathyroid hormone production, typically presents with symptoms such as muscle cramps, tetany, and circumoral numbness due to hypocalcemia.\", \"id\": 1671244560415}"
            },
            {
                "role": "user",
                "content": json.dumps(item[:2], ensure_ascii=False)
            }
        ]
        messages_generate = []
        messages_generate.append(prompt_messages[0])
        messages_generate.append(prompt_messages[1])

    # print(f"messages_generate: {messages_generate}\n") # Print the entire prompt for troubleshooting

    try:
        # Call the OpenAI API with the python sdk
        chat_response = client.chat.completions.create(
            messages=messages_generate,
            model=gpt_version,
            response_format= { "type":"json_object" }
        )

        # Convert the JSON response to a python dictionary
        response_dict = json.loads(chat_response.choices[0].message.content)

        response_dict['id'] = item[0]
        response_dict['interval'] = item[2]
        response_dict['ease'] = item[3]
        response_dict['flags'] = item[4]

        # Define a Pydantic model and validate the response data
        class SentenceResponse(BaseModel):
            # AI generated sentences
            sentence1: str
            sentence2: str
            # Anki note ID
            id: int
            # Fields related to Anki card difficulty
            interval: int
            ease: int
            flags: int
        parsed_response = SentenceResponse(**response_dict)

        print("OpenAI chat completion response")

        print(f"parsed_response: {parsed_response}\n")

        # pydantic parses the json from openai into a python object called parsed_response, for example:
        # sentence1='これは<ruby>全<rt>ぜん</rt></ruby><ruby>然<rt>ぜん</rt></ruby>おいしくない。ちっとも<ruby>満足<rt>まんぞく</rt></ruby>できなかった。' sentence2='This is not delicious at all. I was not satisfied in the slightest.' id=1665999186835

        # Call the next function for the text to speech API
        text_to_speech_ms(parsed_response)

    except Exception as e:
        print("\nError occurred with OpenAI chat completion API...\n")
        print(f"\nAPI response: {chat_response}\n") if 'chat_response' in locals() else None
        traceback.print_exc()
        print("\nExiting the script.\n")
        exit()

# Text to Speech using Microsoft Azure
def text_to_speech_ms(sentences):
    global sentences_html

    print(sentences.sentence1 + " [pause] " + sentences.sentence2)

    # set the language voice - to get the full list of voices you can run this line of code:  print([voice.name for voice in speech_synthesizer.get_voices_async().get().voices])
    # in japanese, clean up furigana formatting and remove second sentence (for now)
    if japanese_language:
        voice = "ja-JP-NanamiNeural"
        text = re.sub(r'<ruby>(.*?)<rt>(.*?)</rt></ruby>', r'\1', sentences.sentence1)
    else:
        voice = "en-US-EmmaNeural"
        text = sentences.sentence1 + " [pause] " + sentences.sentence2
    try:

        # Set the API key and API region
        speech_key, service_region = MICROSOFT_TTS_KEY1, "eastasia"

        # set the file path for the audio file
        subfolder_path = os.path.join(generated_files_path, datetime.datetime.now().strftime("%Y-%m-%d"))
        os.makedirs(subfolder_path, exist_ok=True)
        file_path = os.path.join(subfolder_path, f"speech-{sentences.id}.wav")        

        # create the configuration parameters for the speech sdk
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region) # API key and region
        speech_config.speech_synthesis_voice_name = voice 
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_path) # save as file

        # Generate the speech
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        speech_synthesizer.speak_text_async(text).get()

        print(f"Saved file: {file_path}\n")

        # future - slow down speed of audio https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-speech-synthesis?pivots=programming-language-python&tabs=browserjs%2Cterminal#get-a-result-as-an-in-memory-stream

    except Exception as e:
        print(f"\nAn error occurred with the text to speech api: {e}")
        # print(f"\nAPI response: {response}\n") if 'response' in locals() else None
        traceback.print_exc()
        print("\nExiting the script.\n")
        exit()

    # Build the HTML table row for the sentence
    sentences_html += "<tr>"
    # if japanese, use furigana and 'click to reveal' the sentence.  for all others, build regular html with just sentences.
    if japanese_language:
        sentences_html += "<td>" + sentences.sentence1
        # uncomment the following line if you want to display sentences with 1. Kanji only, 2. Anki furigana separator []
        # sentences_html += "<br>kanji only:  " + re.sub(r'<ruby>(.*?)<rt>(.*?)</rt></ruby>', r'\1', sentences.sentence1) + "<br>anki format:" + re.sub(r'<rt>(.*?)</rt>', r'[\1]', sentences.sentence1)
        sentences_html += "<br><span class=\"small-text\">" + "Interval: " + str(sentences.interval) + " Ease: " + str(sentences.ease) + " Flags: " + str(sentences.flags) + "</span></td>"
        sentences_html += "</td>"
        sentences_html += "<td class=\"clickable hidden-content\">" + sentences.sentence2 + "</td>" # 'click to reveal' for language learning
    else:
        sentences_html += "<td>" + sentences.sentence1 + "</td>"
        sentences_html += "<td>" + sentences.sentence2 + "</td>"
    sentences_html += "<td><audio controls><source src=\"" + f"speech-{sentences.id}.wav" + "\" type=\"audio/mpeg\">The html audio element is not supported.</audio></td>"
    sentences_html += "</tr>"

# call the first function
get_anki_cards() 
