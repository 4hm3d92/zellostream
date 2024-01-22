# zellostream
Python script to stream audio one way to a Zello channel.  Designed for Python 3.X

Acquires audio from an audio file to send to Zello.

Create a developer account with Zello to get credentials.  Set up a different account than what you normally use for Zello, as trying to use this script with the same account that you're using on your mobile device will cause problems.

For Zello consumer network:
- Go to https://developers.zello.com/ and click Login
- Enter your Zello username and password. If you don't have Zello account download Zello app and create one.
- Complete all fields in the developer profile and click Submit
- Click Keys and Add Key
- Copy and save Sample Development Token, Issuer, and Private Key. Make sure you copy each of the values completely using Select All.
- Click Close
- Copy the Private Key into a file called privatekey.pem that's in the same folder as the script.
- The Issuer value goes into config.json.

## config.json
- username:  Zello account username to use for streaming
- password:  Zello account password to use for streaming
- zello_channel:  name of the zello channel to stream to
- issuer:  Issuer credential from Zello account (see above)
- vox_silence_time:  Time in seconds of detected silence before streaming stops. Default: 3
- audio_threshold:  Audio detected above this level will be streamed. Default: 1000
- audio_source: Set to "Audio File"
- in_channel_config: Channel to send. "mono" for mono device. "left", "right" or "mix" for stereo device. Default: mono
- zello_sample_rate: Sample rate of the stream sent to Zello (samples per seconds). Default: 16000
- audio_input_sample_rate: Sample rate of the audio device or UDP stream (samples per seconds). Default: 48000 (set to 8000 or use with UDP stream from trunk-recorder)
- audio_input_channels: Number of audio channels in the device. 1 for mono, 2 for stereo. Default 1
- logging_level: Set Python logging module to this level. Can be "critial", "error", "warning", "info" or "debug". Default "warning".
- zello_work_account_name: Use only when streaming to a ZelloWork account. Include just the zellowork subdomain name here. If you access your zello work account at https://zellostream.zellowork.com, your subdomain would just be zellowork. If left blank, the public zello network will be used.

## Dependencies
### Windows
Requires these DLL files in the same directory:
- opus.dll (renamed from libopus-0.dll)
- libwinpthread-1.dll
- libgcc_s_sjlj-1.dll  

These can be obtained from the 'opusfile' download at http://opus-codec.org/downloads/

Requires pyaudio:
https://people.csail.mit.edu/hubert/pyaudio/

### Required Python packages
```
pip3 install pycryptodome  
pip3 install websocket-client  
pip3 install numpy --upgrade  
pip3 install opuslib  
pip3 install librosa
```

### Installing librosa on a Raspberry Pi
```
sudo apt-get install llvm-11  
LLVM_CONFIG=llvm-config-11 pip3 install llvmlite  
LLVM_CONFIG=llvm-config-11 pip3 install librosa  
sudo apt-get install libblas-dev  
sudo apt-get install libatlas-base-dev
```
### Usage examples
```
python3 zellostream.py --audio_file 2.mp3 --channel IT
python3 zellostream.py --audio_file audio\message.wav --channel Everyone