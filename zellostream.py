import sys
import websocket
import json
import time
import logging
from numpy import frombuffer, array, short, float32, pad
import opuslib
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
import base64
import librosa
import argparse


logging.basicConfig(format='%(asctime)s %(levelname).1s %(funcName)s: %(message)s', level=logging.INFO)
LOG = logging.getLogger('Zellostream')

"""On Windows, requires these DLL files in the same directory:
opus.dll (renamed from libopus-0.dll)
libwinpthread-1.dll
libgcc_s_sjlj-1.dll
These can be obtained from the 'opusfile' download at http://opus-codec.org/downloads/
"""

seq_num = 0


class ConfigException(Exception):
	pass


def get_config():
	config = {}
	f = open("privatekey.pem", "r")
	config["key"] = RSA.import_key(f.read())
	f.close()

	with open("config.json") as f:
		configdata = json.load(f)

	username = configdata.get("username")
	if not username:
		raise ConfigException("ERROR GETTING USERNAME FROM CONFIG FILE")
	config["username"] = username
	password = configdata.get("password")
	if not password:
		raise ConfigException("ERROR GETTING PASSWORD FROM CONFIG FILE")
	config["password"] = password
	issuer = configdata.get("issuer")
	if not issuer:
		raise ConfigException("ERROR GETTING ZELLO ISSUER ID FROM CONFIG FILE")
	config["issuer"] = issuer
	zello_channel = configdata.get("zello_channel")
	if not zello_channel:
		raise ConfigException("ERROR GETTING ZELLO CHANNEL NAME FROM CONFIG FILE")
	config["zello_channel"] = zello_channel
	#config["vox_silence_time"] = configdata.get("vox_silence_time", 3)
	#config["audio_threshold"] = configdata.get("audio_threshold", 1000)
	config["audio_input_channels"] = configdata.get("audio_input_channels", 1)
	config["zello_sample_rate"] = configdata.get("zello_sample_rate", 16000)
	#config["in_channel_config"] = configdata.get("in_channel", "mono")
	config["audio_source"] = configdata.get("audio_source","Audio File")
	config["logging_level"] = configdata.get("logging_level", "warning")
	zello_work = configdata.get("zello_work_account_name")
	if zello_work:
		config["zello_ws_url"] = "wss://zellowork.io/ws/" + zello_work
	else:
		config["zello_ws_url"] = "wss://zello.io/ws"

	return config


def create_zello_jwt(config):
	# Create a Zello-specific JWT.  Can't use PyJWT because Zello doesn't support url safe base64 encoding in the JWT.
	header = {"typ": "JWT", "alg": "RS256"}
	payload = {"iss": config["issuer"], "exp": round(time.time() + 60)}
	signer = pkcs1_15.new(config["key"])
	json_header = json.dumps(header, separators=(",", ":"), cls=None).encode("utf-8")
	json_payload = json.dumps(payload, separators=(",", ":"), cls=None).encode("utf-8")
	h = SHA256.new(base64.standard_b64encode(json_header) + b"." + base64.standard_b64encode(json_payload))
	signature = signer.sign(h)
	jwt = base64.standard_b64encode(json_header) + b"." + base64.standard_b64encode(json_payload) + b"." + base64.standard_b64encode(signature)
	return jwt

def read_audio_file(config,file_path):
	try:
		zello_data, sr = librosa.load(file_path, sr=config["zello_sample_rate"], mono=True, res_type="soxr_vhq")
		#zello_data = librosa.resample(zello_data*20000, orig_sr=sr, target_sr=config["zello_sample_rate"]).astype(short)
		zello_data = (zello_data*32767).astype(short)
		#print(sr)
		return zello_data

	except Exception as ex:
		LOG.error("Error reading audio file: %s", ex)
		return frombuffer(b'', dtype=short)

def create_zello_connection(config, zello_channel):
	try:
		ws = websocket.create_connection(config["zello_ws_url"])
		ws.settimeout(1)
		global seq_num
		seq_num = 1
		send = {}
		send["command"] = "logon"
		send["seq"] = seq_num
		encoded_jwt = create_zello_jwt(config)
		send["auth_token"] = encoded_jwt.decode("utf-8")
		send["username"] = config["username"]
		send["password"] = config["password"]
		send["channel"] = zello_channel
		ws.send(json.dumps(send))
		result = ws.recv()
		data = json.loads(result)
		LOG.info("seq: %d", data.get("seq"))
		seq_num = seq_num + 1
		return ws
	except Exception as ex:
		LOG.error("exception: %s", ex)
		return None


def start_stream(config, ws, zello_channel):
	global seq_num
	start_seq_num = seq_num
	send = {}
	send["command"] = "start_stream"
	send["channel"] = zello_channel
	send["seq"] = seq_num
	seq_num = seq_num + 1
	send["type"] = "audio"
	send["codec"] = "opus"
	# codec_header:
	# base64 encoded 4 byte string: first 2 bytes for sample rate, 3rd for number of frames per packet (1 or 2), 4th for the frame size
	# gd4BPA==  => 0x80 0x3e 0x01 0x3c  => 16000 Hz, 1 frame per packet, 60 ms frame size
	frames_per_packet = 1
	packet_duration = 60
	codec_header = base64.b64encode(
		config["zello_sample_rate"].to_bytes(2, "little") + frames_per_packet.to_bytes(1, "big") + packet_duration.to_bytes(1, "big")
	).decode()
	send["codec_header"] = codec_header
	send["packet_duration"] = packet_duration
	try:
		ws.send(json.dumps(send))
	except Exception as ex:
		LOG.error("send exception %s", ex)
	while True:
		try:
			result = ws.recv()
			data = json.loads(result)
			LOG.debug("data: %s", data)
			if "error" in data.keys():
				LOG.warning("error %s", data["error"])
				if seq_num > start_seq_num + 8:
					LOG.warning("bailing out")
					return None
				time.sleep(0.5)
				send["seq"] = seq_num
				seq_num = seq_num + 1
				ws.send(json.dumps(send))
			if "stream_id" in data.keys():
				stream_id = int(data["stream_id"])
				return stream_id
		except Exception as ex:
			LOG.error("exception %s", ex)
			if seq_num > start_seq_num + 8:
				LOG.warning("bailing out")
				return None
			time.sleep(0.5)
			send["seq"] = seq_num
			seq_num = seq_num + 1
			try:
				ws.send(json.dumps(send))
			except Exception as ex:
				LOG.error("send exception %s", ex)
				return None


def stop_stream(ws, stream_id):
	try:
		send = {}
		send["command"] = "stop_stream"
		send["stream_id"] = stream_id
		ws.send(json.dumps(send))
	except Exception as ex:
		LOG.error("exception: %s", {ex})


def create_encoder(config):
	return opuslib.api.encoder.create_state(config["zello_sample_rate"], config["audio_input_channels"], opuslib.APPLICATION_AUDIO)

def main():
	global processing
	stream_id = None
	processing = True
	zello_ws = None

	parser = argparse.ArgumentParser(description='Zello script to post audio to channels.')

	parser.add_argument('--audio_file', type=str, help='Please input the audio filename.')
	parser.add_argument('--channel', type=str, help='Please input the channel name you want to send the audio to.')

	args = parser.parse_args()

	try:
		config = get_config()
	except ConfigException as ex:
		LOG.critical("configuration error: %s", ex)
		sys.exit(1)
		
	enc = create_encoder(config)	

	log_level = logging.getLevelName(config["logging_level"].upper())
	LOG.setLevel(log_level)
	
	zello_chunk = int(config["zello_sample_rate"] * 0.06)
	
	if config["audio_source"] == "Audio File":
		LOG.info("start audio file read")
		data = read_audio_file(config, args.audio_file)
		if not zello_ws or not zello_ws.connected:
			zello_ws = create_zello_connection(config, args.channel)

		if not zello_ws:
			print("Cannot establish connection")
			time.sleep(1)
			return
		zello_ws.settimeout(1)
		stream_id = start_stream(config, zello_ws, args.channel)
		if not stream_id:
			print("Cannot start stream")
			time.sleep(1)
			return
		print("sending to stream_id " + str(stream_id))
		packet_id = 0
		while processing:
			if len(data)<zello_chunk:
				data = pad(data, (0, zello_chunk-len(data)), 'constant', constant_values=0)
				processing = False
			data2 = data[:zello_chunk - 1].tobytes()
			data = data[zello_chunk:]
			out = opuslib.api.encoder.encode(enc, data2, zello_chunk, len(data2) * 2)
			send_data = bytearray(array([1]).astype(">u1").tobytes())
			send_data = send_data + array([stream_id]).astype(">u4").tobytes()
			send_data = send_data + array([packet_id]).astype(">u4").tobytes()
			send_data = send_data + out
			try:
				nbytes = zello_ws.send_binary(send_data)
				if nbytes == 0:
					print("Binary send error")
					break
			except Exception as ex:
				print(f"Zello error {ex}")
				break
		print("Done sending audio")
		stop_stream(zello_ws, stream_id)
		stream_id = None
		
	else:
		LOG.warning("Invalid Audio Source")

	LOG.info("terminating")
	if zello_ws:
		zello_ws.close()

if __name__ == "__main__":
	main()
