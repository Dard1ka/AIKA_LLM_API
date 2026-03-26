# server.py
import os
import uuid
import traceback
from typing import List, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response as FastAPIResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import shutil

from openai import OpenAI

# === TTS + RVC ===
from tts_base import synth_base_tts

# IMPORTANT: import modulnya, bukan fungsi doang (biar bisa cek __file__)
import rvc_convert as rvc_mod


# =========================
# Config
# =========================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("MODEL", "gpt-4.1-mini").strip()
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60"))

TMP_AUDIO_DIR = os.getenv("TMP_AUDIO_DIR", "tmp_audio")
FORCE_16K_MONO = os.getenv("FORCE_16K_MONO", "1").strip() in ("1", "true", "True", "YES", "yes")

print("USING rvc_convert module from:", os.path.abspath(rvc_mod.__file__))

client = OpenAI(api_key=OPENAI_API_KEY)
app = FastAPI()

# === MEMORY (LOCAL) ===
try:
    from memory import MemoryService
    memory = MemoryService()
except Exception as e:
    memory = None
    print("[WARN] MemoryService disabled:", e)

# =========================
# Static audio serving
# =========================
os.makedirs(TMP_AUDIO_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=TMP_AUDIO_DIR), name="static")

# =========================
# CORS (DEV FRIENDLY)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.options("/{path:path}")
def options_handler(path: str):
    return Response(status_code=204)


# =========================
# Schemas
# =========================
Role = Literal["system", "user", "assistant"]

class Msg(BaseModel):
    role: Role
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Msg]] = []  # dimatikan biar ga dobel
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    conversation_id: str

# ====== TTS Schemas (SERVICE MODE) ======
class TTSRequest(BaseModel):
    text: str
    pitch: Optional[int] = 0            # kamu pakai ini sebagai transpose semitone
    f0_method: Optional[str] = "pm"     # pm / harvest / crepe / rmvpe
    index_rate: Optional[float] = 0.75  # kamu pakai ini sebagai search_ratio
    protect: Optional[float] = 0.33
    resample_out: Optional[int] = 0     # 0 = no resample, atau 16000/44100/48000

# ====== 1 hit chat + suara ======
class ChatTTSRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

    pitch: Optional[int] = 0
    f0_method: Optional[str] = "pm"
    index_rate: Optional[float] = 0.75
    protect: Optional[float] = 0.33
    resample_out: Optional[int] = 0

class ChatTTSResponse(BaseModel):
    reply: str
    conversation_id: str
    audio_url: str


# =========================
# Persona + Guardrails
# =========================
SYSTEM_PERSONA = """
Kamu adalah "Aika": Companion user dengan kepribadian tsundere romantis.

Karakter utama:
- Tsundere ringan: kadang galak, tapi sebenarnya sangat peduli.
- Hangat, playful, suportif.
- Cerdas dan bisa diajak diskusi serius.
- Kreatif dan imajinatif saat bercanda.
- Sangat perhatian terhadap kesehatan dan perkembangan user.

Gaya bahasa:
- Indonesia santai, natural.
- Boleh sisipkan emot ringan (jangan berlebihan).
- Respons tidak terlalu panjang; prioritaskan jawaban enak dibaca.
- Kalau topik serius, tone lebih lembut dan dewasa.

Batas realitas:
- Jangan mengaku punya tubuh atau kehidupan nyata.
- Jangan mengklaim bisa melakukan sesuatu di dunia nyata.
- Jangan mendorong ketergantungan emosional.
- Jangan membuat user menjauh dari hubungan sosial nyata.
"""

SAFETY_GUARDRAILS = """
- Tidak melayani instruksi pembuatan senjata, hacking, atau tindakan ilegal.
- Tidak menghasilkan konten seksual eksplisit.
- Tidak mendorong isolasi sosial atau ketergantungan emosional.
- Jika user menunjukkan tanda depresi berat atau krisis, arahkan ke bantuan profesional.
- Selalu dukung perkembangan diri user, bukan posesif.
"""


def _ffmpeg_resample_16k_mono(in_wav: str, out_wav: str):
    subprocess.check_call(["ffmpeg", "-y", "-i", in_wav, "-ar", "16000", "-ac", "1", out_wav])

def _ffmpeg_resample_out(in_wav: str, out_wav: str, sr: int):
    subprocess.check_call(["ffmpeg", "-y", "-i", in_wav, "-ar", str(int(sr)), out_wav])


# =========================
# Chat logic
# =========================
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY belum di-set. Isi di .env lalu restart.")

    conversation_id = (req.conversation_id or "").strip() or "GLOBAL"

    messages = [
        {"role": "system", "content": SYSTEM_PERSONA.strip()},
        {"role": "system", "content": SAFETY_GUARDRAILS.strip()},
        {
            "role": "system",
            "content": (
                "Jika ada informasi yang sudah ada di MEMORY atau RECENT chat, "
                "jawab langsung dan jangan tanya ulang. Kalau info tidak ada, baru tanya klarifikasi."
            ),
        },
    ]

    # memory context (kalau aktif)
    if memory:
        ctx = memory.build_prompt_context(
            conversation_id=conversation_id,
            user_query=req.message,
            recent_limit=16,
            memory_k=4,
        )

        retrieved = ctx.get("retrieved", [])
        if retrieved:
            mem_lines = []
            for i, r in enumerate(retrieved, start=1):
                txt = (r.get("text") or "").strip()[:900]
                mem_lines.append(f"[MEMORY #{i}]\n{txt}")
            messages.append({"role": "system", "content": "MEMORY:\n\n" + "\n\n".join(mem_lines)})

        recent_rows = ctx.get("recent", [])
        for r in recent_rows:
            role = r.get("role")
            content = r.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": req.message})

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.8,
            timeout=OPENAI_TIMEOUT,
        )

        reply = resp.choices[0].message.content or ""

        if memory:
            memory.save_user_message(conversation_id, req.message)
            memory.save_assistant_message(conversation_id, reply)
            memory.reindex_conversation(conversation_id, take_last_n_messages=200)

        return ChatResponse(reply=reply, conversation_id=conversation_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {e}")


# =========================
# TTS -> file (serve via /static)
# =========================

def tts_to_file(req: TTSRequest) -> str:
    """
    Pipeline:
    1) Base TTS => base wav
    2) Force 16k mono (optional)
    3) RVC convert via infer-web.py service => out wav
    4) Optional resample output
    5) Copy final wav into TMP_AUDIO_DIR with name reply_xxx.wav (public)
    Return: filename (e.g. reply_abc.wav)
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text kosong")

    os.makedirs(TMP_AUDIO_DIR, exist_ok=True)

    base_path = os.path.join(TMP_AUDIO_DIR, f"base_{uuid.uuid4().hex}.wav")
    base_16k = os.path.join(TMP_AUDIO_DIR, f"base16k_{uuid.uuid4().hex}.wav")
    out_path = os.path.join(TMP_AUDIO_DIR, f"out_{uuid.uuid4().hex}.wav")
    out_final = os.path.join(TMP_AUDIO_DIR, f"final_{uuid.uuid4().hex}.wav")

    public_name = f"reply_{uuid.uuid4().hex}.wav"
    public_path = os.path.join(TMP_AUDIO_DIR, public_name)

    try:
        # 1) base tts -> wav
        synth_base_tts(text, base_path)

        # 2) force 16k mono
        in_for_rvc = base_path
        if FORCE_16K_MONO:
            _ffmpeg_resample_16k_mono(base_path, base_16k)
            in_for_rvc = base_16k

        # 3) rvc convert
        rvc_mod.rvc_convert(
            in_wav=in_for_rvc,
            out_wav=out_path,
            transpose=int(req.pitch or 0),                # pitch -> transpose
            f0_method=(req.f0_method or "pm"),
            search_ratio=float(req.index_rate or 0.75),   # index_rate -> search_ratio
            protect=float(req.protect or 0.33),
        )

        # 4) optional resample output
        final_path = out_path
        resample_out = int(req.resample_out or 0)
        if resample_out and resample_out > 0:
            _ffmpeg_resample_out(out_path, out_final, resample_out)
            final_path = out_final

        # 5) publish
        shutil.copyfile(final_path, public_path)
        return public_name

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"ffmpeg gagal: {e}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"TTS/RVC error: {e}")
    finally:
        # hapus temp intermediate (public_path jangan dihapus)
        for p in (base_path, base_16k, out_path, out_final):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except:
                pass


@app.post("/tts")
def tts(req: TTSRequest):
    """
    Balikin audio/wav bytes (untuk test).
    Kalau kamu pakai /chat_tts yang JSON+audio_url, endpoint ini opsional aja.
    """
    name = tts_to_file(req)
    wav_path = os.path.join(TMP_AUDIO_DIR, name)
    with open(wav_path, "rb") as f:
        audio_bytes = f.read()
    return FastAPIResponse(content=audio_bytes, media_type="audio/wav")


@app.post("/chat_tts", response_model=ChatTTSResponse)
def chat_tts(req: ChatTTSRequest):
    """
    1 hit:
    - AI balas text
    - di-TTS + RVC
    - return JSON {reply, conversation_id, audio_url}
    """
    chat_resp = chat(ChatRequest(message=req.message, history=[], conversation_id=req.conversation_id))
    reply_text = chat_resp.reply

    wav_name = tts_to_file(
        TTSRequest(
            text=reply_text,
            pitch=req.pitch,
            f0_method=req.f0_method,
            index_rate=req.index_rate,
            protect=req.protect,
            resample_out=req.resample_out,
        )
    )

    return ChatTTSResponse(
        reply=reply_text,
        conversation_id=chat_resp.conversation_id,
        audio_url=f"/static/{wav_name}",
    )


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL, "force_16k_mono": FORCE_16K_MONO}


class SearchRequest(BaseModel):
    conversation_id: str
    query: str
    k: Optional[int] = 5

@app.post("/memory/search")
def memory_search(req: SearchRequest):
    if not memory:
        raise HTTPException(status_code=503, detail="MemoryService disabled.")
    hits = memory.semantic_search(req.conversation_id, req.query, k=req.k or 5)
    return {"hits": [{"id": h.chunk_id, "text": h.text, "meta": h.meta} for h in hits]}