from RealtimeSTT import AudioToTextRecorder
import pyaudiowpatch as pyaudio
from queue import Queue
import numpy as np
import samplerate
import threading
import wave
import time
import time
import os

from chat_history import MESSAGE_TYPE, ROLE
from textual_ui import *

# Required for resampling speaker audio
#   as realtimeSST requires specifically 16khz sound
CHUNK = 5024
SPEAKER_RATE = 16000
SPEAKER_CHANNELS = 1
MIC_RATE = 16000
MIC_CHANNELS = 1
resampler = samplerate.Resampler(converter_type='sinc_fastest')
TARGET_RATE = 16000

VOICETOTEXT_MODEL_REALTIME = 'tiny'
VOICETOTEXT_MODEL = 'base'
VOICETOTEXT_LANGUAGE = 'en'

speaker_recorder = None  
mic_recorder = None  

message_queue = Queue()

def realtime_transcription_speaker(text):
    message_queue.put({
        "role": ROLE.USER, 
        "transcription_type": MESSAGE_TYPE.REALTIME, 
        "content": text
    })
    

def realtime_transcription_mic(text):
    message_queue.put({
        "role": ROLE.ASSISTANT, 
        "transcription_type": MESSAGE_TYPE.REALTIME, 
        "content": text
    })


def write_chunk_to_file(data, rate, channels=1, out_file_name='qqqq.wav'):
    # Save chunk to a temp WAV file
    # Used for debugging only
    with wave.open(out_file_name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(TARGET_RATE)
        wf.writeframes(data)

def record_audio_speaker(in_data, frame_count, time_info, status):
    """
        Resamples buffer to TARGET_RATE and feeds it to RealTimeSST
    """
    global speaker_recorder
    audio_np = np.frombuffer(in_data, dtype=np.int16)
    
    if SPEAKER_CHANNELS > 1:
        audio_np = np.reshape(audio_np, (-1, SPEAKER_CHANNELS))
        audio_np = audio_np[:, 0]

    audio_np = audio_np.astype(np.float32) / 32768.0
    resampled = resampler.process(audio_np, TARGET_RATE / SPEAKER_RATE)
    audio_np = (resampled * 32768.0).astype(np.int16).tobytes()

    speaker_recorder.feed_audio(audio_np, original_sample_rate=16000)
        
    return (in_data, pyaudio.paContinue)

# def record_audio_mic(in_data, frame_count, time_info, status):
#     global mic_recorder
#     audio_np = np.frombuffer(in_data, dtype=np.int16)
    
#     if MIC_CHANNELS > 1:
#         audio_np = np.reshape(audio_np, (-1, MIC_CHANNELS))
#         audio_np = audio_np[:, 0]

#     audio_np = audio_np.astype(np.float32) / 32768.0
#     resampled = resampler.process(audio_np, TARGET_RATE / MIC_RATE)
#     audio_np = (resampled * 32768.0).astype(np.int16).tobytes()

#     # write_chunk_to_file(audio_np, TARGET_RATE, 1, 'qqqq.wav')
#     mic_recorder.feed_audio(audio_np, original_sample_rate=16000)
        
#     return (in_data, pyaudio.paContinue)


def get_default_speaker(p):
    """
        Gets device id (and the sample rate and number of channels)
        of the speaker that is currently set to system default.
    """
    global SPEAKER_RATE, SPEAKER_CHANNELS
    try:
        # Get default WASAPI info
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        exit()

    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

    if not default_speakers["isLoopbackDevice"]:
        for loopback in p.get_loopback_device_info_generator():
            """
            Try to find loopback device with same name(and [Loopback suffix]).
            Unfortunately, this is the most adequate way at the moment.
            """
            if default_speakers["name"] in loopback["name"]:
                default_speakers = loopback
                break
        else:
            exit()
    
    SPEAKER_RATE = int(default_speakers["defaultSampleRate"])
    SPEAKER_CHANNELS = default_speakers["maxInputChannels"]

    speakers_stream = p.open(
        format=pyaudio.paInt16,
        channels=SPEAKER_CHANNELS,
        rate=SPEAKER_RATE,
        frames_per_buffer=CHUNK,
        input=True,
        input_device_index=default_speakers["index"],
        stream_callback=record_audio_speaker
    ) 

    return speakers_stream


# Configuration for RealTimeSST
recorder_config = {
    'spinner': False,
    'model': VOICETOTEXT_MODEL, # or large-v2 or deepdml/faster-whisper-large-v3-turbo-ct2 or ...
    'download_root': '.', # default download root location. Ex. ~/.cache/huggingface/hub/ in Linux
    'realtime_model_type': VOICETOTEXT_MODEL_REALTIME, # or small.en or distil-small.en or ...
    'language': VOICETOTEXT_LANGUAGE,
    'silero_sensitivity': 0.05,
    'webrtc_sensitivity': 3,
    'post_speech_silence_duration': 1,
    'min_length_of_recording': 1.1,        
    'min_gap_between_recordings': 0,                
    'enable_realtime_transcription': True,
    'realtime_processing_pause': 1,
    'silero_deactivity_detection': True,
    'early_transcription_on_silence': 0,
    'beam_size': 5,
    'beam_size_realtime': 3,
    'batch_size': 0,
    'realtime_batch_size': 0,        
    'no_log_file': True,
    'initial_prompt_realtime': (
        "End incomplete sentences with ellipses.\n"
        "Examples:\n"
        "Complete: The sky is blue.\n"
        "Incomplete: When the sky...\n"
        "Complete: She walked home.\n"
        "Incomplete: Because he...\n"
    ),
    'silero_use_onnx': True,
    'use_microphone': False,
    'faster_whisper_vad_filter': False,
    # 'level': logging.DEBUG
}

def poll_speaker_recorder(r):
    """
        This will poll the RealTimeSST service (the one responsible for the speaker)
        for new (final, non-realtime) messages and put them into the queue
    """
    while True:
        # time.sleep(0.1)
        text = r.text()
        message_queue.put({
            "role": ROLE.USER, 
            "transcription_type": MESSAGE_TYPE.FINAL, 
            "content": text
        })

def speaker_simulate_noise(r):
    # The recorder will not spit out the final result until the buffer is full.
    # so we force it full with empty audio.
    silent_buffer = (b'\x00\x00') * 1024
    while True:
        r.feed_audio(silent_buffer, original_sample_rate=16000)
        time.sleep(0.3)


def poll_mic_recorder(r):
    """
        This will poll the RealTimeSST service (the one responsible for the mic)
        for new (final, non-realtime) messages and put them into the queue
    """
    while True:
        # time.sleep(0.1)
        text = r.text()
        message_queue.put({
            "role": ROLE.ASSISTANT, 
            "transcription_type": MESSAGE_TYPE.FINAL, 
            "content": text
        })


def main():
    global speaker_recorder, mic_recorder
    p = pyaudio.PyAudio()

    speaker_recorder_config = recorder_config.copy()
    speaker_recorder_config['on_realtime_transcription_stabilized'] = realtime_transcription_speaker
    speaker_recorder = AudioToTextRecorder(**speaker_recorder_config) 

    mic_recorder_config = recorder_config.copy()
    mic_recorder_config['on_realtime_transcription_stabilized'] = realtime_transcription_mic
    mic_recorder_config['use_microphone'] = True
    mic_recorder = AudioToTextRecorder(**mic_recorder_config) 

    speakers_stream = get_default_speaker(p)
    print("🔴 Listening to the speakers")

    speaker_record_thread = threading.Thread(target=poll_speaker_recorder, args=[speaker_recorder], daemon=True)
    speaker_record_thread.start()
    speaker_noise_thread = threading.Thread(target=speaker_simulate_noise, args=[speaker_recorder], daemon=True)
    speaker_noise_thread.start()

    mic_record_thread = threading.Thread(target=poll_mic_recorder, args=[mic_recorder], daemon=True)
    mic_record_thread.start()

    return (speakers_stream, speaker_recorder, mic_recorder)


if __name__ == '__main__':
    speakers_stream, speaker_recorder, mic_recorder = main()
    app = ChatApp(message_queue)
    app.run()
    # speaker_recorder.shutdown()
    # speakers_stream.stop_stream()
    # speakers_stream.close()
    # mic_recorder.shutdown()
    exit()