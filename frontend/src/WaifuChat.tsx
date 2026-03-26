import { useEffect, useMemo, useRef, useState } from "react";

type ChatMsg = { role: "user" | "assistant"; content: string };

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const STORAGE_KEY = "waifu_chat_state_v1";

declare global {
  interface Window {
    webkitSpeechRecognition?: any;
    SpeechRecognition?: any;
  }
}

// ===== Voice player (play blob wav from backend) =====
function useWaifuVoice() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  const stop = () => {
    try {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
    } catch {}
    try {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    } catch {}
    urlRef.current = null;
  };

  // Unlock autoplay (call on user click once)
  const unlock = async () => {
    try {
      const a = new Audio();
      a.src =
        "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAgD4AAAB9AAACABAAZGF0YQAAAAA=";
      await a.play();
      a.pause();
    } catch {}
  };

  const speakBlob = async (blob: Blob) => {
    stop();
    const url = URL.createObjectURL(blob);
    urlRef.current = url;

    const audio = new Audio(url);
    audioRef.current = audio;

    audio.onended = () => {
      try {
        if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      } catch {}
      urlRef.current = null;
    };

    await audio.play();
  };

  useEffect(() => () => stop(), []);

  return { stop, unlock, speakBlob };
}

type ChatTTSJson = {
  reply?: string;
  conversation_id?: string;
  audio_url?: string; // "/static/reply_xxx.wav"
};

type PersistedState = {
  messages: ChatMsg[];
  conversationId: string | null;
  ttsEnabled: boolean;
  sttEnabled: boolean;
};

export default function WaifuChat() {
  // ✅ default greeting (dipakai kalau localStorage kosong)
  const DEFAULT_MESSAGES: ChatMsg[] = [
    { role: "assistant", content: "Hmph… akhirnya kamu datang juga. Mau ngobrol apa? 😤✨" },
  ];

  const [messages, setMessages] = useState<ChatMsg[]>(DEFAULT_MESSAGES);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);

  // toggles
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [sttEnabled, setSttEnabled] = useState(true);

  const { stop, unlock, speakBlob } = useWaifuVoice();

  // SpeechRecognition
  const SpeechRecognition = useMemo(
    () => window.SpeechRecognition || window.webkitSpeechRecognition,
    []
  );
  const recognitionRef = useRef<any>(null);
  const [isListening, setIsListening] = useState(false);

  // ====== Scroll handling (pintar) ======
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const [stickToBottom, setStickToBottom] = useState(true);
  const [showJumpBtn, setShowJumpBtn] = useState(false);

  const scrollToBottom = (smooth = true) => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  };

  // detect user scroll (kalau user naik ke atas, jangan auto-scroll)
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;

    const onScroll = () => {
      const threshold = 120; // px dari bawah dianggap "masih di bawah"
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      const atBottom = distanceFromBottom < threshold;

      setStickToBottom(atBottom);
      setShowJumpBtn(!atBottom);
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // auto-scroll hanya kalau user memang di bawah
  useEffect(() => {
    if (stickToBottom) scrollToBottom(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, thinking]);

  // ====== ✅ Persist state: LOAD once ======
  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;

    try {
      const parsed = JSON.parse(raw) as PersistedState;

      if (Array.isArray(parsed.messages) && parsed.messages.length > 0) {
        setMessages(parsed.messages);
      } else {
        setMessages(DEFAULT_MESSAGES);
      }

      if (typeof parsed.conversationId === "string" || parsed.conversationId === null) {
        setConversationId(parsed.conversationId ?? null);
      }

      if (typeof parsed.ttsEnabled === "boolean") setTtsEnabled(parsed.ttsEnabled);
      if (typeof parsed.sttEnabled === "boolean") setSttEnabled(parsed.sttEnabled);

      // pastikan langsung ke bawah saat load pertama
      setTimeout(() => scrollToBottom(false), 0);
    } catch {
      // kalau corrupt, fallback ke greeting default
      setMessages(DEFAULT_MESSAGES);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ====== ✅ Persist state: SAVE on change ======
  useEffect(() => {
    const data: PersistedState = {
      messages,
      conversationId,
      ttsEnabled,
      sttEnabled,
    };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch {}
  }, [messages, conversationId, ttsEnabled, sttEnabled]);

  // ====== STT init ======
  useEffect(() => {
    if (!SpeechRecognition) return;

    const rec = new SpeechRecognition();
    rec.lang = "id-ID";
    rec.continuous = false;
    rec.interimResults = true;

    rec.onstart = () => setIsListening(true);
    rec.onend = () => setIsListening(false);
    rec.onerror = () => setIsListening(false);

    rec.onresult = (event: any) => {
      let finalTranscript = "";
      let interimTranscript = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalTranscript += t;
        else interimTranscript += t;
      }

      setInput(() => {
        const merged = (finalTranscript || interimTranscript).trim();
        return merged.length ? merged : "";
      });
    };

    recognitionRef.current = rec;
  }, [SpeechRecognition]);

  const canSTT = !!SpeechRecognition;

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;

    stop();
    await unlock();

    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setInput("");
    setThinking(true);

    try {
      const res = await fetch(`${API_BASE}/chat_tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          conversation_id: conversationId,
          pitch: 0,
          f0_method: "rmvpe",
          index_rate: 0.7,
          protect: 0.2,
          resample_out: 0,
        }),
      });

      if (!res.ok) {
        const t = await res.text();
        console.error("chat_tts failed:", t);
        throw new Error(`HTTP ${res.status}`);
      }

      // ✅ chat_tts JSON
      const data = (await res.json()) as ChatTTSJson;
      console.log("chat_tts JSON:", data);

      const replyText = (data.reply ?? "").trim();
      const cid = data.conversation_id ?? null;

      // ✅ update conversationId (jangan cuma kalau null — update saja biar konsisten)
      if (cid) setConversationId(cid);

      setMessages((m) => [...m, { role: "assistant", content: replyText || "(no reply)" }]);

      // ✅ audio fetch dari /static/...
      if (ttsEnabled && data.audio_url) {
        const audioRes = await fetch(`${API_BASE}${data.audio_url}`, { method: "GET" });
        if (!audioRes.ok) {
          console.warn("audio fetch failed:", audioRes.status);
        } else {
          const blob = await audioRes.blob();
          try {
            await speakBlob(blob);
          } catch (e) {
            console.warn("Audio play blocked or failed:", e);
          }
        }
      }
    } catch (e) {
      console.error(e);
      setMessages((m) => [...m, { role: "assistant", content: "Tch… ada error. Cek console ya. 😒" }]);
    } finally {
      setThinking(false);
    }
  }

  function toggleMic() {
    if (!recognitionRef.current) return;

    stop();

    if (isListening) recognitionRef.current.stop();
    else {
      setInput("");
      recognitionRef.current.start();
    }
  }

  const clearChat = () => {
    stop();
    setMessages(DEFAULT_MESSAGES);
    setConversationId(null);
    setThinking(false);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
    setTimeout(() => scrollToBottom(false), 0);
  };

  return (
    <div className="min-h-screen w-full bg-[#070A12] text-white overflow-hidden relative">
      <div className="pointer-events-none absolute -top-40 -left-40 h-[420px] w-[420px] rounded-full blur-3xl opacity-40 bg-gradient-to-br from-cyan-400 via-fuchsia-500 to-purple-600" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-[520px] w-[520px] rounded-full blur-3xl opacity-35 bg-gradient-to-br from-pink-500 via-purple-600 to-cyan-400" />

      <div className="sticky top-0 z-10 backdrop-blur-xl bg-white/5 border-b border-white/10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="h-11 w-11 rounded-2xl bg-white/10 border border-white/15 grid place-items-center shadow-lg">
            <span className="text-xl">💠</span>
          </div>
          <div className="flex-1">
            <div className="font-semibold tracking-wide">Aika • Waifu AI</div>
            <div className="text-xs text-white/70 flex items-center gap-2">
              <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_18px_rgba(52,211,153,0.8)]" />
              {thinking ? "Thinking…" : "Online"} {conversationId ? "• Linked Memory" : "• GLOBAL Memory"}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={async () => {
                await unlock();
                setTtsEnabled((v) => !v);
                if (ttsEnabled) stop();
              }}
              className={`px-3 py-2 rounded-xl border text-xs transition ${
                ttsEnabled ? "bg-white/10 border-white/20" : "bg-white/5 border-white/10 text-white/60"
              }`}
              title="Toggle Waifu voice"
            >
              🔊 Voice {ttsEnabled ? "ON" : "OFF"}
            </button>

            <button
              onClick={() => setSttEnabled((v) => !v)}
              className={`px-3 py-2 rounded-xl border text-xs transition ${
                sttEnabled ? "bg-white/10 border-white/20" : "bg-white/5 border-white/10 text-white/60"
              }`}
              title="Toggle mic input"
            >
              🎙️ STT {sttEnabled ? "ON" : "OFF"}
            </button>

            <button
              onClick={clearChat}
              className="px-3 py-2 rounded-xl border text-xs transition bg-white/5 border-white/10 text-white/70 hover:border-white/25"
              title="Clear chat (local only)"
            >
              🧹 Clear
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl shadow-[0_0_40px_rgba(0,0,0,0.35)] overflow-hidden relative">
          {/* Chat scroller */}
          <div ref={scrollerRef} className="p-5 h-[70vh] overflow-y-auto space-y-4">
            {messages.map((m, idx) => (
              <div key={idx} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={[
                    "max-w-[78%] rounded-3xl px-4 py-3 text-sm leading-relaxed",
                    m.role === "user"
                      ? "bg-gradient-to-br from-cyan-400/20 to-purple-500/20 border border-cyan-300/25 shadow-[0_0_20px_rgba(34,211,238,0.15)]"
                      : "bg-gradient-to-br from-pink-500/15 to-fuchsia-500/15 border border-pink-300/20 shadow-[0_0_22px_rgba(236,72,153,0.12)]",
                  ].join(" ")}
                >
                  {m.content}
                </div>
              </div>
            ))}

            {thinking && (
              <div className="flex justify-start">
                <div className="max-w-[78%] rounded-3xl px-4 py-3 text-sm bg-white/5 border border-white/10">
                  <span className="opacity-80">Aika lagi mikir…</span>
                  <span className="inline-block ml-2 animate-pulse">✨</span>
                </div>
              </div>
            )}
          </div>

          {/* Jump-to-bottom button */}
          {showJumpBtn && (
            <button
              onClick={() => scrollToBottom(true)}
              className="absolute right-4 bottom-24 h-10 w-10 rounded-2xl border border-white/15 bg-white/10 hover:bg-white/15 transition shadow-lg"
              title="Scroll to bottom"
            >
              ↓
            </button>
          )}

          <div className="border-t border-white/10 bg-white/3 backdrop-blur-xl p-4">
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={sttEnabled ? "Ketik… atau tekan mic dan ngomong." : "Ketik pesan kamu…"}
                  className="w-full min-h-[52px] max-h-[140px] resize-none rounded-2xl bg-white/5 border border-white/10 focus:border-white/25 outline-none px-4 py-3 text-sm"
                />
                <div className="mt-2 text-[11px] text-white/55">
                  {sttEnabled && canSTT
                    ? isListening
                      ? "🎙️ Listening…"
                      : "🎙️ Mic siap."
                    : !canSTT
                    ? "Browser belum support STT."
                    : "🎙️ STT dimatikan."}
                </div>
              </div>

              <button
                onClick={toggleMic}
                disabled={!sttEnabled || !canSTT}
                className={[
                  "h-12 w-12 rounded-2xl grid place-items-center border transition",
                  !sttEnabled || !canSTT
                    ? "bg-white/5 border-white/10 text-white/35 cursor-not-allowed"
                    : isListening
                    ? "bg-gradient-to-br from-pink-500/30 to-fuchsia-500/30 border-pink-300/30 shadow-[0_0_24px_rgba(236,72,153,0.25)]"
                    : "bg-gradient-to-br from-cyan-400/20 to-purple-500/20 border-cyan-300/25 hover:border-white/30",
                ].join(" ")}
                title="Mic"
              >
                {isListening ? "🛑" : "🎙️"}
              </button>

              <button
                onClick={() => sendMessage(input)}
                disabled={thinking}
                className={[
                  "h-12 px-5 rounded-2xl border font-semibold text-sm transition",
                  thinking
                    ? "bg-white/5 border-white/10 text-white/40 cursor-not-allowed"
                    : "bg-gradient-to-br from-cyan-400/25 to-pink-500/25 border-white/15 hover:border-white/30 shadow-[0_0_24px_rgba(34,211,238,0.18)]",
                ].join(" ")}
              >
                Send ✨
              </button>
            </div>

            <div className="mt-3 flex items-center justify-between text-[11px] text-white/45">
              <div>Tips: klik Send sekali untuk unlock audio browser.</div>
              <div className="opacity-75">Futuristic • Cute • Glass UI</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}