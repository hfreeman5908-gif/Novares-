import streamlit as st
import base64
import requests
from groq import Groq
from PIL import Image
import io
import random
import qrcode

# ── Keys ──────────────────────────────────────────────
GROQ_KEY  = st.secrets["GROQ_KEY"]
IMGBB_KEY = st.secrets["IMGBB_KEY"]
client = Groq(api_key=GROQ_KEY)

# ── Seiten-Config ──────────────────────────────────────
st.set_page_config(page_title="Novares | Smart Recycling", page_icon="♻️", layout="centered")

# ── CSS ────────────────────────────────────────────────
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
# 4 Behälter im Mülleimer
# Wertstoffe = Plastik + Metall zusammen (Gelbe Tonne)
KATEGORIEN = {
    "Wertstoffe": {"farbe": "#e65c00", "tonne": "🟡 Behälter 1 — Wertstoffe",  "bg": "#fff3e0"},
    "Papier":     {"farbe": "#1565c0", "tonne": "🔵 Behälter 2 — Papier",      "bg": "#e3f2fd"},
    "Bio":        {"farbe": "#6d4c41", "tonne": "🟤 Behälter 3 — Bio",         "bg": "#efebe9"},
    "Restmüll":   {"farbe": "#37474f", "tonne": "⚫ Behälter 4 — Restmüll",    "bg": "#f5f5f5"},
}

# Mapping: KI-Ergebnis → Behälter (Glas & Metall → Wertstoffe)
MAPPING = {
    "Wertstoffe": "Wertstoffe",
    "Plastik":    "Wertstoffe",
    "Metall":     "Wertstoffe",
    "Glas":       "Wertstoffe",
    "Papier":     "Papier",
    "Bio":        "Bio",
    "Restmüll":   "Restmüll",
}

# ── Fakten ─────────────────────────────────────────────
FAKTEN = {
    "Wertstoffe": [
        "🔄 Plastik, Metall und Glas gehören alle in den Wertstoff-Behälter.",
        "⚡ Recyceltes Aluminium spart 95% der Energie gegenüber Neuproduktion.",
        "♾️ Glas kann unendlich oft recycelt werden ohne Qualitätsverlust.",
        "🌊 Jedes Jahr landen 8 Millionen Tonnen Plastik im Meer.",
    ],
    "Plastik": [
        "🌊 Jedes Jahr landen 8 Millionen Tonnen Plastik im Meer.",
        "♻️ Aus 25 PET-Flaschen kann ein Fleece-Pullover hergestellt werden.",
        "⏳ Eine Plastikflasche braucht bis zu 450 Jahre um sich zu zersetzen.",
        "🛢️ Recyceltes Plastik spart bis zu 80% Energie gegenüber Neuproduktion.",
    ],
    "Papier": [
        "🌳 Aus 100 kg Altpapier können 85 kg neues Papier hergestellt werden.",
        "💧 Recyclingpapier verbraucht 70% weniger Wasser als frisches Papier.",
        "📦 Deutschland recycelt über 80% seines Papiers — Weltspitze!",
        "🌲 Eine Tonne Recyclingpapier rettet ca. 17 Bäume.",
    ],
    "Glas": [
        "♾️ Glas kann unendlich oft recycelt werden ohne Qualitätsverlust.",
        "⚡ Recyceltes Glas schmilzt bei niedrigeren Temperaturen — spart Energie.",
        "🏺 Die ältesten Glasobjekte der Welt sind über 3.500 Jahre alt.",
        "🌡️ Beim Glasrecycling wird 20% weniger CO₂ ausgestoßen.",
    ],
    "Metall": [
        "🔄 Aluminium kann endlos recycelt werden — in nur 60 Tagen Kreislauf.",
        "⚡ Recyceltes Aluminium spart 95% der Energie gegenüber Neuproduktion.",
        "🚗 Ein Schrottauto liefert genug Stahl für 13 neue Fahrräder.",
        "💰 Metall ist das wertvollste Recyclingmaterial überhaupt.",
    ],
    "Bio": [
        "🌱 Aus Biomüll entsteht wertvoller Kompost für die Landwirtschaft.",
        "⚡ Biogas aus organischen Abfällen kann Strom und Wärme erzeugen.",
        "🍎 Ein Drittel aller Lebensmittel weltweit wird weggeworfen.",
        "🌍 Kompostierung reduziert Methan-Emissionen aus Deponien erheblich.",
    ],
    "Restmüll": [
        "🔥 Restmüll wird in Deutschland meist thermisch verwertet — also verbrannt.",
        "📉 Je weniger Restmüll, desto besser für die Umweltbilanz.",
        "🤔 Vieles im Restmüll könnte eigentlich recycelt werden — genau hinsehen!",
        "🏭 Aus Restmüll-Verbrennung wird immerhin noch Energie gewonnen.",
    ],
}

# ── API Funktionen ─────────────────────────────────────
def upload_bild(img_bytes):
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_KEY, "image": b64})
    antwort = r.json()
    if "data" not in antwort:
        st.error(f"imgbb Fehler: {antwort}")
        st.stop()
    return antwort["data"]["url"]

def analysiere_muell(img_url):
    prompt = """Analysiere das Bild. Antworte NUR in diesem exakten Format, keine extra Erklaerungen:

GEGENSTAND: [was es ist, kurz auf Deutsch]
MATERIAL: [das genaue Material: Plastik, Papier, Glas, Metall, Bio oder Restmuell]
BEHAELTER: [wohin es gehoert — NUR eines dieser 4: Wertstoffe, Papier, Bio, Restmuell]
  Regel: Plastik + Metall + Glas = Wertstoffe
  Regel: Papier + Karton = Papier
  Regel: Essensreste + Pflanzen = Bio
  Regel: alles andere = Restmuell
KOMPLEX: [JA wenn Trennung noetig z.B. Deckel ab, Inhalt leeren — sonst NEIN]
SCHRITT1: [Trennungsschritt 1, nur wenn KOMPLEX=JA, sonst leer lassen]
SCHRITT2: [Trennungsschritt 2, falls vorhanden, sonst leer lassen]
SCHRITT3: [Trennungsschritt 3, falls vorhanden, sonst leer lassen]"""

    r = client.chat.completions.create(
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": img_url}}
            ]
        }],
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        max_completion_tokens=250,
    )
    text = r.choices[0].message.content.strip()
    gegenstand, kategorie, komplex, schritte = "Unbekannt", "Restmüll", False, []
    for zeile in text.split("\n"):
        zeile = zeile.strip()
        if zeile.startswith("GEGENSTAND:"):
            gegenstand = zeile.replace("GEGENSTAND:", "").strip()
        elif zeile.startswith("KATEGORIE:"):
            kat = zeile.replace("KATEGORIE:", "").strip()
            # Normalisierung: Restmuell -> Restmüll
            kat = kat.replace("Restmuell", "Restmüll")
            if kat in KATEGORIEN:
                kategorie = kat
        elif zeile.startswith("KOMPLEX:"):
            komplex = "JA" in zeile.upper()
        elif zeile.startswith("SCHRITT1:"):
            s = zeile.replace("SCHRITT1:", "").strip()
            if s:
                schritte.append(s)
        elif zeile.startswith("SCHRITT2:"):
            s = zeile.replace("SCHRITT2:", "").strip()
            if s:
                schritte.append(s)
        elif zeile.startswith("SCHRITT3:"):
            s = zeile.replace("SCHRITT3:", "").strip()
            if s:
                schritte.append(s)
    return gegenstand, kategorie, komplex, schritte

def erstelle_qr_png(url):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a5c2a", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ── Session State ──────────────────────────────────────
if "zaehler" not in st.session_state:
    st.session_state.zaehler = {k: 0 for k in KATEGORIEN}
if "letztes_ergebnis" not in st.session_state:
    st.session_state.letztes_ergebnis = None

# ── Modus-Schalter ─────────────────────────────────────
if "modus" not in st.session_state:
    st.session_state.modus = "foto"

col_l, col_r = st.columns(2)
with col_l:
    if st.button("📷 Foto-Modus", use_container_width=True,
                 type="primary" if st.session_state.modus == "foto" else "secondary"):
        st.session_state.modus = "foto"
        st.rerun()
with col_r:
    if st.button("🎥 Live-Modus", use_container_width=True,
                 type="primary" if st.session_state.modus == "live" else "secondary"):
        st.session_state.modus = "live"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ── FOTO-MODUS ─────────────────────────────────────────
if st.session_state.modus == "foto":
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
                gegenstand, kategorie, komplex, schritte = analysiere_muell(url)
                st.session_state.zaehler[kategorie] += 1
                st.session_state.letztes_ergebnis = {
                    "gegenstand": gegenstand,
                    "kategorie": kategorie,
                    "komplex": komplex,
                    "schritte": schritte,
                    "fakt": random.choice(FAKTEN[kategorie]),
                }
            except Exception as e:
                st.error(f"Fehler: {e}")

# ── LIVE-MODUS ─────────────────────────────────────────
else:
    st.markdown("""
    <div style="background:#f5f5f5;border-radius:16px;padding:32px;text-align:center;
                border:2px dashed #ccc;margin-top:8px;">
        <div style="font-size:2.5rem;margin-bottom:12px;">🚧</div>
        <div style="font-size:1.1rem;font-weight:700;color:#555;margin-bottom:8px;">
            Live-Modus — kommt bald
        </div>
        <div style="font-size:0.9rem;color:#888;">
            Wird aktiviert sobald der Mülleimer fertig gebaut ist.<br>
            Bitte nutze vorerst den 📷 Foto-Modus.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Ergebnis anzeigen ──────────────────────────────────
if st.session_state.letztes_ergebnis:
    erg = st.session_state.letztes_ergebnis
    akt_kat = erg["kategorie"]
    k = KATEGORIEN[akt_kat]

    # Ergebnis-Box
    st.markdown(f"""
    <div class="result-box" style="background:{k['bg']}; border-color:{k['farbe']}33;">
        <div class="obj-name">🔍 Erkannt: <b>{erg['gegenstand']}</b></div>
        <div class="kategorie" style="color:{k['farbe']};">{akt_kat}</div>
        <div class="tonne">{k['tonne']}</div>
        <div class="badge" style="background:{k['farbe']};">✓ Erkannt</div>
    </div>
    """, unsafe_allow_html=True)

    # Trennungsanleitung
    if erg.get("komplex") and erg.get("schritte"):
        farbe = k["farbe"]
        teile = []
        for i, s in enumerate(erg["schritte"]):
            teile.append(
                '<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px;">'
                '<div style="background:' + farbe + ';color:white;border-radius:50%;'
                'width:24px;height:24px;min-width:24px;display:flex;'
                'align-items:center;justify-content:center;'
                'font-size:0.75rem;font-weight:700;">' + str(i+1) + '</div>'
                '<div style="font-size:0.9rem;color:#333;padding-top:3px;">' + s + '</div>'
                '</div>'
            )
        schritte_html = "".join(teile)
        st.markdown(
            '<div style="background:#fffde7;border-left:5px solid #f9a825;'
            'border-radius:12px;padding:16px 20px;margin-top:14px;">'
            '<div style="font-size:0.78rem;color:#888;font-weight:600;margin-bottom:10px;">'
            '✂️ TRENNUNGSANLEITUNG</div>'
            + schritte_html +
            '</div>',
            unsafe_allow_html=True
        )

    # Recycling-Fakt
    st.markdown(f"""
    <div style="background:{k['bg']};border-left:5px solid {k['farbe']};
                border-radius:12px;padding:16px 20px;margin-top:14px;">
        <div style="font-size:0.78rem;color:#888;margin-bottom:4px;font-weight:600;">
            💡 WUSSTEST DU?
        </div>
        <div style="font-size:0.95rem;color:#333;line-height:1.5;">{erg['fakt']}</div>
    </div>
    """, unsafe_allow_html=True)

    # Korrektur
    st.markdown("<br>", unsafe_allow_html=True)
    kat_liste = list(KATEGORIEN.keys())
    neue_kat = st.selectbox("✏️ Kategorie falsch? Hier korrigieren:", kat_liste, index=kat_liste.index(akt_kat))
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
        <div style="background:white;border-radius:12px;padding:16px;text-align:center;
                    border-top:4px solid {farbe};box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:12px;">
            <div style="font-size:1.6rem;font-weight:800;color:{farbe};">{anzahl}</div>
            <div style="font-size:0.8rem;color:#777;">{kat}</div>
        </div>
        """, unsafe_allow_html=True)

if st.button("🔄 Statistik zurücksetzen"):
    st.session_state.zaehler = {k: 0 for k in KATEGORIEN}
    st.session_state.letztes_ergebnis = None
    st.rerun()

# ── QR-Code ────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📲 App teilen")

try:
    APP_URL = st.context.url
except Exception:
    APP_URL = "http://localhost:8501"

st.markdown("""
<div style="background:white;border-radius:20px;padding:28px;text-align:center;
            box-shadow:0 4px 24px rgba(0,0,0,0.08);border:2px solid #e0f2e9;">
    <div style="font-size:1.1rem;font-weight:700;color:#1a5c2a;margin-bottom:4px;">📱 App direkt öffnen</div>
    <div style="font-size:0.82rem;color:#888;">Einfach mit dem Handy scannen</div>
</div>
""", unsafe_allow_html=True)

qr_png = erstelle_qr_png(APP_URL)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image(qr_png, use_container_width=True)
    st.download_button("⬇️ QR-Code herunterladen", data=qr_png,
                       file_name="novares_qr.png", mime="image/png", use_container_width=True)

st.markdown(f"""
<p style="text-align:center;font-size:0.78rem;color:#aaa;margin-top:8px;">🔗 {APP_URL}</p>
""", unsafe_allow_html=True)
