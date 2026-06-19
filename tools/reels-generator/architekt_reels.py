import os
import json
import requests
import subprocess
import glob
from pathlib import Path

# ==========================================
# KONFIGURACJA
# ==========================================

def _load_elevenlabs_key() -> str:
    """Klucz z ENV lub plików .env (~/Desktop/.env, repo .env) — bez hardcodu w repo."""
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if key:
        return key
    candidates = [
        Path.home() / "Desktop" / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

ELEVENLABS_API_KEY = _load_elevenlabs_key()
# Szow (Maverick) — z brand/agent_voices.yaml; nadpisz ELEVENLABS_VOICE_ID w .env
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "V33LkP9pVLdcjeB2y5Na").strip() or "V33LkP9pVLdcjeB2y5Na"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3" # Upewnij się, że masz pobrany model (np. ollama run llama3)

DIR_INPUT = "input"
DIR_ASSETS = "assets"
DIR_TEMP = "temp"
DIR_OUTPUT = "output"

# Upewnij się, że foldery istnieją
for d in [DIR_INPUT, DIR_ASSETS, DIR_TEMP, DIR_OUTPUT]:
    os.makedirs(d, exist_ok=True)

# ==========================================
# FUNKCJE POMOCNICZE
# ==========================================

def parse_script_with_ollama(script_text):
    """
    Używa lokalnego modelu Ollama do wyciągnięcia tekstu AUDIO oraz NAPISÓW z surowego skryptu.
    """
    print("[*] Parsowanie skryptu przez Ollama...")
    prompt = f"""
    Jesteś asystentem, który analizuje skrypt wideo. 
    Z poniższego tekstu wyciągnij tylko i wyłącznie treść, którą ma przeczytać lektor (AUDIO), 
    oraz główny krótki napis, który ma pojawić się na ekranie (NAPIS).
    
    Zwróć wynik w formacie JSON:
    {{
        "audio": "tekst do przeczytania",
        "napis": "krótki napis na ekran"
    }}
    
    Skrypt:
    {script_text}
    """
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        parsed = json.loads(data["response"])
        audio = parsed.get("audio") or parsed.get("AUDIO")
        napis = parsed.get("napis") or parsed.get("NAPIS") or "Seria CIEŃ"
        if not audio:
            raise KeyError("audio")
        print("  [+] Pomyślnie sparsowano skrypt.")
        return audio, napis
    except Exception as e:
        print(f"  [!] Błąd Ollama: {e}")
        print("  [!] Upewnij się, że aplikacja Ollama jest uruchomiona na macOS.")
        return None, None

def parse_script_fallback(script_text: str) -> tuple[str, str]:
    """Fallback bez LLM — [NAPIS: …] + reszta jako audio."""
    napis = "Seria CIEŃ"
    audio_parts: list[str] = []
    for line in script_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("[NAPIS:") and line.endswith("]"):
            napis = line[len("[NAPIS:") : -1].strip()
            continue
        audio_parts.append(line)
    return " ".join(audio_parts), napis

def _ffmpeg_has_drawtext() -> bool:
    r = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True)
    return "drawtext" in (r.stdout or "")

def generate_voiceover(text, output_path):
    """
    Generuje plik audio przy użyciu ElevenLabs API.
    """
    print("[*] Generowanie głosu lektora (ElevenLabs)...")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.3, # Mniejsza stabilność dla bardziej emocjonalnego/mrocznego tonu
            "similarity_boost": 0.7,
            "style": 0.2,
            "use_speaker_boost": True
        }
    }
    
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"  [+] Zapisano audio do: {output_path}")
        return True
    else:
        print(f"  [!] Błąd ElevenLabs: {response.text}")
        return False

def get_audio_duration(audio_path):
    """Pobiera długość audio w sekundach używając ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return float(result.stdout)

def build_video(audio_path, napis, output_path):
    """
    Składa ostateczne wideo używając FFmpeg (poprzez subprocess dla precyzyjnej kontroli).
    Bierze pierwszy plik .mp4 z folderu assets, zapętla go do długości audio,
    dodaje ścieżkę dźwiękową, nakłada mroczny filtr i napis na środku ekranu.
    """
    print("[*] Montaż wideo (FFmpeg)...")
    
    # Szukaj wideo w assets
    videos = glob.glob(f"{DIR_ASSETS}/*.mp4")
    if not videos:
        print("  [!] Brak plików wideo (.mp4) w folderze 'assets'. Dodaj plik wygenerowany przez Grok Imagine.")
        return False
        
    video_input = videos[0]
    print(f"  [+] Używam pliku wideo: {video_input}")
    
    duration = get_audio_duration(audio_path)
    print(f"  [+] Długość docelowa wideo: {duration:.2f} s")
    
    font_path = "/System/Library/Fonts/Helvetica.ttc"
    # yuvj420p (full range) z Grok/cien0 — bez in_range=full filtr eq gryzie obraz do czerni.
    base_vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "scale=in_range=full:out_range=full,"
        "eq=gamma=1.4:brightness=0.16:contrast=1.22:saturation=1.1"
    )
    if _ffmpeg_has_drawtext():
        safe_napis = napis.replace("'", "\\'").replace(":", "\\:")
        vf_filter = (
            f"{base_vf},"
            f"drawtext=fontfile='{font_path}':text='{safe_napis}':fontcolor=white:fontsize=70:"
            "x=(w-text_w)/2:y=(h-text_h)/2:shadowcolor=black:shadowx=3:shadowy=3:alpha=0.9"
        )
    else:
        print("  [!] FFmpeg bez filtra drawtext — montaż bez napisu na ekranie.")
        vf_filter = base_vf
    
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", # Zapętlaj wideo nieskończenie
        "-i", video_input,    # Wejście wideo
        "-i", audio_path,     # Wejście audio
        "-t", str(duration),  # Utnij na długości audio
        "-vf", vf_filter,     # Filtry wizualne
        "-c:v", "libx264",    # Kodek wideo
        "-color_range", "pc",  # pełny zakres — tekst/napisy z Grok nie giną w cieniu
        "-preset", "fast",
        "-c:a", "aac",        # Kodek audio
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",          # Upewnij się, że kończy się z najkrótszym strumieniem (z limitem -t to zadziała)
        output_path
    ]
    
    print("  [+] Uruchamiam FFmpeg (to może potrwać kilka sekund)...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if result.returncode == 0:
        print(f"  [+] Wideo wygenerowane pomyślnie: {output_path}")
        return True
    else:
        print(f"  [!] Błąd FFmpeg:\n{result.stderr.decode('utf-8')}")
        return False

# ==========================================
# GŁÓWNA LOGIKA
# ==========================================

def main():
    print("=== ARCHITEKT WOLNOŚCI - GENERATOR REELS ===")
    
    script_file = os.path.join(DIR_INPUT, "script.txt")
    if not os.path.exists(script_file):
        print(f"[!] Nie znaleziono pliku {script_file}.")
        print("Utwórz go i wklej tam skrypt wygenerowany wcześniej.")
        return
        
    with open(script_file, "r", encoding="utf-8") as f:
        raw_script = f.read()
        
    audio_text, napis = parse_script_with_ollama(raw_script)
    
    if not audio_text:
        print("[!] Parsowanie Ollama nie powiodło się — fallback z pliku script.txt.")
        audio_text, napis = parse_script_fallback(raw_script)
        
    print(f"  -> AUDIO: {audio_text}")
    print(f"  -> NAPIS: {napis}")
    
    audio_path = os.path.join(DIR_TEMP, "voiceover.mp3")
    output_path = os.path.join(DIR_OUTPUT, "final_reel.mp4")
    
    # 1. Generuj Audio
    if generate_voiceover(audio_text, audio_path):
        # 2. Montuj Wideo
        build_video(audio_path, napis, output_path)
    
    print("=== PROCES ZAKOŃCZONY ===")

if __name__ == "__main__":
    main()
