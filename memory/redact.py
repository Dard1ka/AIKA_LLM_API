import re

# Pola sederhana (pemula-friendly). Nanti bisa kamu tambah.
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(\+?\d[\d\-\s]{7,}\d)\b")
TOKEN_RE = re.compile(r"\b(sk-[A-Za-z0-9]{10,}|AIza[0-9A-Za-z\-_]{20,})\b")  # contoh OpenAI/GCP style
PASSWORD_HINT_RE = re.compile(r"(?i)\b(password|passwd|pwd|api key|apikey|token)\b\s*[:=]\s*\S+")
OTP_RE = re.compile(r"\b\d{4,8}\b")  # hati-hati: ini bisa kena angka biasa; dipakai terbatas

def redact_text(text: str) -> str:
    if not text:
        return text

    t = text
    t = EMAIL_RE.sub("[REDACTED_EMAIL]", t)
    t = TOKEN_RE.sub("[REDACTED_TOKEN]", t)
    t = PASSWORD_HINT_RE.sub("[REDACTED_SECRET]", t)
    t = PHONE_RE.sub("[REDACTED_PHONE]", t)

    # OTP: hanya redact kalau ada konteks OTP/kode (biar angka biasa ga ikut)
    if re.search(r"(?i)\b(otp|kode|verification|verifikasi)\b", text):
        t = OTP_RE.sub("[REDACTED_CODE]", t)

    return t
