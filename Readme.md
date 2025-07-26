# Interview Coach

This tool is created to provide the user with realtime feedback during a (job) interview around how it's going. By analyzing the (real-time captured) interview transcript, it can analyze the tone of the dialogue and make suggestions around what to focus on more and what to leave behind.

In contrast to some other popular tools, this one is not only free to use and modify, but also supports hooking up to locally hosted Ollama instance to avoid paying OpenAI (more on that later)

## Structure

- **`app.py`** is the entry point to the, well, app
- **`gpt_request`** contains 

## Installing

The app is only tested on Windows (10) OS.

### Prequisites

First and foremost, I suggest you use [Windows Terminal](https://learn.microsoft.com/en-us/windows/terminal/install) as `Textual` uses special symbols that regular command prompt is unable to display.

Then install the python packages from the [requirements.txt](requirements.txt). They would be
* `numpy` for matrix operations during resampling of the audio buffer (see `record_audio_speaker` method in [app.py](app.py))
* `samplerate` for the actual resampling mentioned above
* `textual` and `textual-dev` for terminal GUI
* `pyaudiowpatch` is the only way I could hook into the computer's sound and mic without blocking other software. It's in a [small repo](https://github.com/s0d3s/PyAudioWPatch/) I found.
* And the special guest - [RealTimeSTT](https://github.com/KoljaB/RealtimeSTT) . This is the core of the application that takes care of the voice-to-text (transcription). The author has done a great job and the reason why the app works so seamlessly is precisely thanks to the author. The library isn't 100% plug and play imo, so I had to maneuvr around to integrate it into my use-case. For instance, it doesn't support listening to the speakers and the way to accomplish it is a bit of work, but I figured it out. Anyway, follow the installation instructions from that page. You do not **have to** have a cuda-capable GPU to run this since we're using the `tiny` and `base` models (in contrast to `large-v2` that the author uses in their examples) but it would be beneficial. Otherwise, make sure you have at least a mid-range CPU. Potato PC owners - sorry :( .  

## Launching

The default settings of the app are
- Uses ChatGPT as the default provider (line 25 in [textual_ui.py](textual_ui.py) )
 - so place your API Key into a file called `apikey` in the root directory of the project
 - you may leave the default `LLM_MODEL` as `'gpt-4.1-nano'`
- Uses your default microphone and speakers to listen to the interview
 - Functionality to choose input/output device will be added later
- `SYSTEM_PROMPT` is already set to a reasonable default value but you may modify it (line 8 in [gpt_request.py](gpt_request.py) ) or create a `systemprompt.txt` file (in the root folder) to override it
- You may change the default voice-to-text model to something heavier (`VOICETOTEXT_MODEL` and `VOICETOTEXT_MODEL_REALTIME` in [app.py](app.py) ), but in my experience, the `base` model is good enough. The default transcription language (`VOICETOTEXT_LANGUAGE`) is `en`glish.

The entrypoint to the tool is [app.py](app.py). **Please make sure to navigate to the root directory of the project before launching**

## Using
The conversation transcription is always on and is always real-time

Use the following shortcuts
* `F7` to perform a call the LLM. For Ollama, it will be _stream_-ed .You may press `F7` again to stop generating the current response and generate a new one. The LLM will receive the transcript up to the **latest stable phrase by the interviewer** meaning unfinished speech and/or last interviewee-s phrase will not be counted.
* `F8` to clear the chat history completely (the system prompt will stay)
* `+` to increase the portion of the "GPT Suggestion" container and `-` to decrease it
* Use `Ctrl +` and `Ctrl -` (system default) to increase / decrease the size of your terminal

## Roadmap

If the project gets reasonable popularity, I'm aiming to add several features including
* Pasting from clipboard
* Correctly handling both participants speaking at the same time (right now phrases can only be complete and whicever started first, goes first. In practice this means that if you reply "yes" 3 times midway into a long sentence by the interviewer, the transcript would look like "interviewer: [long sentence]", "interviewee: yes" , "interviewee: yes" , "interviewee: yes"). This would involve writing a fork to RealTimeSTT to ask it to return timestamps per word (it can do that) and dividing a long phrase into 2 parts if an _interruption_ by the other speaker was detected. 
* Hide from screen-sharing (needs re-writing to PyQt6)
* Screenshot analyzing (for coding tasks)

## Alternative usage

If the system prompt is modified, you can force the LLM to do other things than mild suggestions, however remember that interview fraud is a thing and the more those things get used, the more the companies will be inclined to move away from online interviews in favor of face to face, stop hiring remotely etc. 

## Using Ollama as the LLM

My experience (4080 super GPU) is that gaming GPUs are slow and waiting 2-3 seconds for a response is not always reasonable. However the functionality is included and you may tweak it at your convenience and use the entire thing completely for free. 

## Final remarks

I am not a software engineer, therefore my code abides to neither the best practices, nor common sense (sometimes). I did the best from what I knew, and suggestions would be appreciated. Otherwise to all comments like "this code is shit", my answer is "yes, it is, but it runs."