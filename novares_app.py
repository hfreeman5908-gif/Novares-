import streamlit as st
import base64
import requests
from groq import Groq
from PIL import Image
import io
import qrcode
import qrcode.image.svg

# ── Keys ──────────────────────────────────────────────
GROQ_KEY = st.secrets["GROQ_KEY"]
IMGBB_KEY = st.secrets["IMGBB_KEY"]
client = Groq(api_key=GROQ_KEY)

# ── Seiten-Config ──────────────────────────────────────
st.set_page_config(
    page_title="Novares | Smart Recycling",
    page_icon="♻️",
    layout="centered"
)

# ── CSS Design ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
* { font-family: 'Inter', sans-serif; }
.stApp { background-color: #f0faf4; }
.header {
    background: linear-gradient(135deg, #1a5c2a, #2e8b47);
    border-radius: 20px; padding: 28px 32px; margin-bottom: 28px;
    display: flex; align-items: center; gap: 18px;
}
.logo-text { color: white; font-size: 2.4rem; font-weight: 800; letter-spacing: -1px; margin: 0; }
.logo-sub  { color: #a8dbb8; font-size: 0.85rem; margin: 0; }
.logo-icon { font-size: 3rem; }
.result-box {
    border-radius: 20px; padding: 28px; text-align: center; margin-top: 20px;
    border: 2px solid rgba(0,0,0,0.06); background: white;
    box-shadow: 0 4px 24px rgba(0,0,0,0.06);
}
.obj-name  { font-size: 1.1rem; color: #555; margin-bottom: 6px; }
.kategorie { font-size: 2rem; font-weight: 800; margin: 8px 0; }
.tonne     { font-size: 1rem; color: #777; margin-top: 4px; }
.badge     { display: inline-block; padding: 6px 18px; border-radius: 100px;
              color: white; font-weight: 700; font-size: 0.85rem; margin-top: 12px; }
.qr-box {
    background: white; border-radius: 20px; padding: 28px;
    text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    border: 2px solid #e0f2e9;
}
.qr-title  { font-size: 1.1rem; font-weight: 700; color: #1a5c2a; margin-bottom: 4px; }
.qr-sub    { font-size: 0.82rem; color: #888; margin-bottom: 16px; }
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────
st.markdown("""
<div class="header">
    <div class="logo-icon">♻️</div>
    <div>
        <p class="logo-text">NOVARES</p>
        <p class="logo-sub">Smart Recycling — KI-gestützte Müllerkennung</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Kategorien ─────────────────────────────────────────
KATEGORIEN = {
    "Plastik":  {"farbe": "#e65c00", "tonne": "🟡 Gelbe Tonne",    "bg": "#fff3e0"},
    "Papier":   {"farbe": "#1565c0", "tonne": "🔵 Blaue Tonne",    "bg": "#e3f2fd"},
    "Glas":     {"farbe": "#2e7d32", "tonne": "🟢 Glascontainer",  "bg": "#e8f5e9"},
    "Metall":   {"farbe": "#546e7a", "tonne": "🟡 Gelbe Tonne",    "bg": "#eceff1"},
    "Bio":      {"farbe": "#6d4c41", "tonne": "🟤 Braune Tonne",   "bg": "#efebe9"},
    "Restmüll": {"farbe": "#37474f", "tonne": "⚫ Schwarze Tonne", "bg": "#f5f5f5"},
}

# ── QR-Code Generator ──────────────────────────────────
def erstelle_qr_png(url: str) -> bytes:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a5c2a", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ── API Funktionen ─────────────────────────────────────
def upload_bild(img_bytes):
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    r = requests.post("https://api.imgbb.com/1/upload",
                      data={"key": IMGBB_KEY, "image": b64})
    antwort = r.json()
    if "data" not in antwort:
        st.error(f"imgbb Fehler: {antwort}")
        st.stop()
    return antwort["data"]["url"]

def analysiere_muell(img_url):
    r = client.chat.completions.create(
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": """Analysiere das Bild in zwei Teilen:
1. Was ist der Gegenstand? (ein kurzer Satz auf Deutsch)
2. In welche Kategorie gehört er? Wähle NUR aus: Plastik, Papier, Glas, Metall, Bio, Restmüll

Antworte genau in diesem Format:
GEGENSTAND: [was es ist]
KATEGORIE: [eine der 6 Kategorien]"""},
                {"type": "image_url", "image_url": {"url": img_url}}
            ]
        }],
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        max_completion_tokens=80,
    )
    text = r.choices[0].message.content.strip()
    gegenstand, kategorie = "Unbekannt", "Restmüll"
    for zeile in text.split("\n"):
        if "GEGENSTAND:" in zeile:
            gegenstand = zeile.replace("GEGENSTAND:", "").strip()
        if "KATEGORIE:" in zeile:
            kat = zeile.replace("KATEGORIE:", "").strip()
            if kat in KATEGORIEN:
                kategorie = kat
    return gegenstand, kategorie

# ── Session State ──────────────────────────────────────
if "zaehler" not in st.session_state:
    st.session_state.zaehler = {k: 0 for k in KATEGORIEN}
if "letztes_ergebnis" not in st.session_state:
    st.session_state.letztes_ergebnis = None

# ── Kamera Input ───────────────────────────────────────
st.markdown("### 📸 Halte einen Gegenstand in die Kamera")
foto = st.camera_input("Kamera", label_visibility="collapsed")

if foto:
    with st.spinner("🔍 KI analysiert..."):
        try:
            img = Image.open(foto)
            img.thumbnail((800, 800))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=50)
            img_bytes = buf.getvalue()

            url = upload_bild(img_bytes)
            gegenstand, kategorie = analysiere_muell(url)

            st.session_state.letztes_ergebnis = {"gegenstand": gegenstand, "kategorie": kategorie}
            st.session_state.zaehler[kategorie] += 1

        except Exception as e:
            st.error(f"Fehler: {e}")

# ── Ergebnis + Korrektur ───────────────────────────────
if st.session_state.letztes_ergebnis:
    erg = st.session_state.letztes_ergebnis
    akt_kat = erg["kategorie"]
    k = KATEGORIEN[akt_kat]

    st.markdown(f"""
    <div class="result-box" style="background:{k['bg']}; border-color:{k['farbe']}33;">
        <div class="obj-name">🔍 Erkannt: <b>{erg['gegenstand']}</b></div>
        <div class="kategorie" style="color:{k['farbe']};">{akt_kat}</div>
        <div class="tonne">{k['tonne']}</div>
        <div class="badge" style="background:{k['farbe']};">✓ Erkannt</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    kat_liste = list(KATEGORIEN.keys())
    neue_kat = st.selectbox("✏️ Kategorie falsch? Hier korrigieren:",
                             kat_liste, index=kat_liste.index(akt_kat))
    if neue_kat != akt_kat:
        if st.button("✅ Korrektur bestätigen"):
            st.session_state.zaehler[akt_kat] = max(0, st.session_state.zaehler[akt_kat] - 1)
            st.session_state.zaehler[neue_kat] += 1
            st.session_state.letztes_ergebnis["kategorie"] = neue_kat
            st.success(f"✔️ Korrigiert: {akt_kat} → {neue_kat}")
            st.rerun()

# ── Statistik ──────────────────────────────────────────
st.markdown("---")
st.markdown("### 📊 Heutige Statistik")
cols = st.columns(3)
for i, (kat, anzahl) in enumerate(st.session_state.zaehler.items()):
    farbe = KATEGORIEN[kat]["farbe"]
    with cols[i % 3]:
        st.markdown(f"""
        <div style="background:white; border-radius:12px; padding:16px;
                    text-align:center; border-top: 4px solid {farbe};
                    box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom:12px;">
            <div style="font-size:1.6rem; font-weight:800; color:{farbe};">{anzahl}</div>
            <div style="font-size:0.8rem; color:#777;">{kat}</div>
        </div>
        """, unsafe_allow_html=True)

if st.button("🔄 Statistik zurücksetzen"):
    st.session_state.zaehler = {k: 0 for k in KATEGORIEN}
    st.session_state.letztes_ergebnis = None
    st.rerun()

# ── QR-Code Sektion ────────────────────────────────────
st.markdown("---")
st.markdown("### 📲 App teilen")

APP_URL = "https://novaresapp.streamlit.app"  # ← hier eure echte URL eintragen

st.markdown(f"""
<div class="qr-box">
    <div class="qr-title">📱 App direkt öffnen</div>
    <div class="qr-sub">Einfach mit dem Handy scannen — kein Link tippen nötig</div>
</div>
""", unsafe_allow_html=True)

qr_png = erstelle_qr_png(APP_URL)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image(qr_png, use_container_width=True)
    st.download_button(
        label="⬇️ QR-Code herunterladen",
        data=qr_png,
        file_name="novares_qr.png",
        mime="image/png",
        use_container_width=True,
    )

st.markdown(f"""
<p style="text-align:center; font-size:0.78rem; color:#aaa; margin-top:8px;">
    🔗 {APP_URL}
</p>
""", unsafe_allow_html=True)
