# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# <code>
import azure.cognitiveservices.speech as speechsdk
import os

MICROSOFT_TTS_KEY1 = os.environ.get('MICROSOFT_TTS_KEY1')

# Set the API key and API region
speech_key, service_region = MICROSOFT_TTS_KEY1, "eastasia"

# create the configuration parameters for the speech sdk
speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region) # API key and region
speech_config.speech_synthesis_voice_name = "ja-JP-NanamiNeural" # Voice language - to get the full list of voices run this line of code:  print([voice.name for voice in speech_synthesizer.get_voices_async().get().voices])
audio_config = speechsdk.audio.AudioOutputConfig(filename="soundfile.wav") # save as file

# Creates a speech synthesizer using the default speaker as audio output.
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

# speech_synthesizer.speak_text_async("I'm excited to try text to speech")

# Receives a text from console input.
print("Type some text that you want to speak...")
text = input()

result = speech_synthesizer.speak_text_async(text).get()

# Checks result.
if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("Speech synthesized to speaker for text [{}]".format(text))
elif result.reason == speechsdk.ResultReason.Canceled:
    cancellation_details = result.cancellation_details
    print("Speech synthesis canceled: {}".format(cancellation_details.reason))
    if cancellation_details.reason == speechsdk.CancellationReason.Error:
        if cancellation_details.error_details:
            print("Error details: {}".format(cancellation_details.error_details))
    print("Did you update the subscription info?")

# next step - slow down speed of audio
    # https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-speech-synthesis?pivots=programming-language-python&tabs=browserjs%2Cterminal#get-a-result-as-an-in-memory-stream

# </code>
