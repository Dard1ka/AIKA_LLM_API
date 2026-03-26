from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Optional

import requests

RVC_URL = os.getenv("RVC_URL", "http://127.0.0.1:7865").rstrip("/")
API_NAME = os.getenv("RVC_API_CONVERT", "infer_convert").lstrip("/")


class RVCError(RuntimeError):
    pass


def _ensure_file(p: str | Path) -> str:
    p = str(Path(p).expanduser().resolve())
    if not os.path.isfile(p):
        raise FileNotFoundError(f"File not found: {p}")
    return p


def _pick_audio_path(obj: Any) -> Optional[str]:
    """
    Gradio bisa balikin:
    - string path
    - dict {"name": "...", "data": "..."} (kadang)
    - dict {"path": "..."} (kadang)
    - list/tuple nested
    """
    if obj is None:
        return None
    if isinstance(obj, str) and obj.lower().endswith((".wav", ".flac", ".mp3", ".m4a", ".ogg")):
        return obj
    if isinstance(obj, dict):
        for k in ("path", "name"):
            v = obj.get(k)
            if isinstance(v, str) and v.lower().endswith((".wav", ".flac", ".mp3", ".m4a", ".ogg")):
                return v
    if isinstance(obj, (list, tuple)):
        for it in obj:
            p = _pick_audio_path(it)
            if p:
                return p
    return None


def _post_run(api_name: str, data: list, debug: bool = False) -> dict:
    """
    Endpoint yang benar:
      POST /run/{api_name}
    Body: {"data":[...]}
    """
    url = f"{RVC_URL}/run/{api_name.lstrip('/')}"
    payload = {"data": data}
    r = requests.post(url, json=payload, timeout=600)
    if debug:
        print("DEBUG POST:", url)
        print("DEBUG status:", r.status_code)
        txt = r.text
        if len(txt) > 1500:
            txt = txt[:1500] + " ... <truncated>"
        print("DEBUG resp:", txt)
    if r.status_code >= 400:
        raise RVCError(f"HTTP {r.status_code} from {url}\nResponse:\n{r.text}")
    return r.json()


def rvc_convert(
    *,
    in_wav: str | Path,
    out_wav: str | Path,
    index_path: str = "",
    f0_method: str = "rmvpe",
    speaker_id: int = 0,
    transpose: int = 0,
    search_ratio: float = 0.75,
    filter_radius: int = 3,
    resample_sr: int = 0,
    vol_env: float = 0.25,
    protect: float = 0.33,
    f0_curve_path: str = "",   # optional (kalau kosong -> None)
    debug: bool = False,
) -> str:
    """
    Mapping parameter sesuai /info named endpoint "/infer_convert" (Gradio 3.34):
    1) Speaker ID (slider)
    2) audio file path (textbox)
    3) transpose (number)
    4) f0 curve file (File) -> None kalau tidak dipakai
    5) f0 method (radio)
    6) index_path textbox
    7) dropdown index path
    8) search ratio
    9) filter radius
    10) resample sr
    11) vol env
    12) protect
    """
    in_wav = _ensure_file(in_wav)
    out_wav = str(Path(out_wav).expanduser().resolve())
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)

    index_path = (index_path or "").strip()
    if not index_path:
        # kalau kosong, biarin dropdown yang isi (logs\\model/model.index biasanya)
        dropdown_index = "logs\\model/model.index"
    else:
        dropdown_index = ""  # pakai textbox index_path

    # f0 curve optional: kalau kamu mau isi, kamu harus upload via /upload,
    # tapi untuk sekarang kita NONE dulu (sama seperti UI kalau tidak dipakai)
    f0_curve = None
    if f0_curve_path.strip():
        # kalau kamu beneran mau pakai: minimal kita kirim string path (kadang bisa)
        f0_curve = str(Path(f0_curve_path).expanduser().resolve())

    data = [
        int(speaker_id),     # 1
        str(in_wav),         # 2
        int(transpose),      # 3
        f0_curve,            # 4
        str(f0_method),      # 5
        str(index_path),     # 6
        str(dropdown_index), # 7
        float(search_ratio), # 8
        float(filter_radius),# 9
        int(resample_sr),    # 10
        float(vol_env),      # 11
        float(protect),      # 12
    ]

    if debug:
        print("Loaded as API:", RVC_URL)
        print("DEBUG api_name:", API_NAME)
        print("DEBUG data_len:", len(data))
        print("DEBUG data:", data)

    result = _post_run(API_NAME, data, debug=debug)

    out_data = result.get("data")
    if out_data is None:
        raise RVCError(f"No 'data' in response. raw={result!r}")

    # returns: [ "Output information", "Audio file (path/dict)" ]
    audio_obj = out_data[1] if isinstance(out_data, list) and len(out_data) >= 2 else out_data
    audio_path = _pick_audio_path(audio_obj)
    if not audio_path:
        raise RVCError(f"RVC returned no audio path. out_data={out_data!r}")

    audio_path = _ensure_file(audio_path)
    shutil.copyfile(audio_path, out_wav)
    return out_wav