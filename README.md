# ai-anki
Integration between Anki local DB and OpenAI APIs for sentence generation and text to speech

Pre-requisites:
Anki client app installed locally
OpenAI API key

Steps:
Manually synchronize the client so it has the latest card updates
Make backup copy of anki database
Query the set of cards for AI augmentation
Use chat completion API to generate sentence variations
Use text to speech API and fluent-ffmpeg to generate mp3 file
Create new card in Anki DB with the sentence variations and mp3 file
