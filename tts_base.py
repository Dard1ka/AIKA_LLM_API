# tts_base.py
import os
import subprocess
import uuid

# Voice Indonesia yang enak:
# - id-ID-GadisNeural (cewek)
# - id-ID-ArdiNeural (cowok)
EDGE_VOICE = os.getenv("EDGE_TTS_VOICE", "id-ID-GadisNeural")
EDGE_RATE = os.getenv("EDGE_TTS_RATE", "+0%")  # "-10%" kalau mau lebih pelan

def synth_base_tts(text: str, out_wav: str):
    """
    Generate base TTS -> WAV 16k mono (stabil buat RVC).
    Output: out_wav (WAV 16k mono)
    """
    os.makedirs(os.path.dirname(out_wav) or ".", exist_ok=True)

    # bikin temp mp3
    tmp_mp3 = out_wav + f".{uuid.uuid4().hex}.tmp.mp3"

    # 1) edge-tts -> mp3
    # edge-tts CLI: edge-tts --voice ... --rate ... --text ... --write-media file.mp3
    subprocess.check_call([
        "edge-tts",
        "--voice", EDGE_VOICE,
        "--rate", EDGE_RATE,
        "--text", text,
        "--write-media", tmp_mp3,
    ])

    # 2) ffmpeg convert -> WAV 16k mono
    subprocess.check_call([
        "ffmpeg", "-y",
        "-i", tmp_mp3,
        "-ar", "16000",
        "-ac", "1",
        out_wav
    ])

    # cleanup
    try:
        if os.path.exists(tmp_mp3):
            os.remove(tmp_mp3)
    except:
        pass