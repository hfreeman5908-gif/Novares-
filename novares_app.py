import streamlit as st
import base64
import requests
from groq import Groq
from PIL import Image
import io
import random
import qrcode
import serial
import serial.tools.list_ports



# ── Seiten-Config ──────────────────────────────────────
st.set_page_config(page_title="Novares | Smart Recycling", page_icon="♻", layout="centered")

# ── Kategorien ─────────────────────────────────────────
KATEGORIEN = {
    "Plastik":      {"farbe": "#e65c00", "tonne": "Behaelter 1 - Nur Plastik",         "bg": "#fff3e0"},
    "Papier":       {"farbe": "#1565c0", "tonne": "Behaelter 2 - Nur Papier",           "bg": "#e3f2fd"},
    "Bio":          {"farbe": "#6d4c41", "tonne": "Behaelter 3 - Nur Kompostierbares",  "bg": "#efebe9"},
    "Restmuell":    {"farbe": "#37474f", "tonne": "Behaeltxaer 4 - Restmuell",            "bg": "#f5f5f5"},
    "Sonderabfall": {"farbe": "#b71c1c", "tonne": "Sonderabfall - Nicht in den Muell!", "bg": "#ffebee"},
}

MAPPING = {
    "Plastik": "Plastik", "Metall": "Restmuell", "Glas": "Restmuell",
    "Wertstoffe": "Plastik", "Papier": "Papier", "Karton": "Restmuell",
    "Pappe": "Papier", "Bio": "Bio", "Biomuell": "Bio",
    "Restmuell": "Restmuell", "Restmüll": "Restmuell", "Sonderabfall": "Sonderabfall",
}

FAKTEN = {
    "Plastik": [
        "Jedes Jahr landen 8 Millionen Tonnen Plastik im Meer.",
        "Aus 25 PET-Flaschen kann ein Fleece-Pullover hergestellt werden.",
        "Eine Plastikflasche braucht bis zu 450 Jahre um sich zu zersetzen.",
        "Recyceltes Plastik spart bis zu 80% Energie gegenueber Neuproduktion.",
    ],
    "Papier": [
        "Aus 100 kg Altpapier koennen 85 kg neues Papier hergestellt werden.",
        "Recyclingpapier verbraucht 70% weniger Wasser als frisches Papier.",
        "Deutschland recycelt ueber 80% seines Papiers.",
        "Eine Tonne Recyclingpapier rettet ca. 17 Baeume.",
    ],
    "Bio": [
        "Aus Biomuell entsteht wertvoller Kompost fuer die Landwirtschaft.",
        "Biogas aus organischen Abfaellen kann Strom und Waerme erzeugen.",
        "Ein Drittel aller Lebensmittel weltweit wird weggeworfen.",
        "Kompostierung reduziert Methan-Emissionen erheblich.",
    ],
    "Restmuell": [
        "Restmuell wird in Deutschland meist verbrannt.",
        "Je weniger Restmuell, desto besser fuer die Umwelt.",
        "Vieles im Restmuell koennte eigentlich recycelt werden.",
        "Aus Restmuell-Verbrennung wird immerhin noch Energie gewonnen.",
    ],
    "Sonderabfall": [
        "Batterien enthalten Schwermetalle die das Grundwasser vergiften koennen.",
        "Medikamente niemals in den Ausguss - sie verschmutzen das Trinkwasser.",
        "Elektroschrott enthaelt wertvolle Rohstoffe wie Gold und Kupfer.",
        "Farben und Lacke sind Sondermuell - zum Wertstoffhof bringen!",
    ],
}

# ── Impact-Daten ───────────────────────────────────────
# Quellen: DIW 2021, Umweltbundesamt 2023, Wien Biotonnen-Studie, EVS Saar
CO2_PRO_KG   = {"Plastik": 1.5, "Papier": 0.15, "Bio": 0.1, "Restmuell": 0.0, "Sonderabfall": 0.0}
GEWICHT_KG   = {"Plastik": 0.05, "Papier": 0.1, "Bio": 0.15, "Restmuell": 0.1, "Sonderabfall": 0.05}
KOSTEN_EUR_KG = 0.44  # Restmuell-Entsorgung EVS Saar

# Vergleichswerte fuer CO2-Kontext (belegte Quellen)
# Auto: 150g CO2/km (Durchschnitt PKW, co2online.de / UBA)
# Zug:  36g CO2/km (UBA 2018, Fernverkehr)
# Netflix: 400g CO2/Stunde (stromee.de)
CO2_AUTO_PRO_KM   = 150   # Gramm
CO2_ZUG_PRO_KM    = 36    # Gramm
CO2_NETFLIX_PRO_H = 400   # Gramm

def co2_vergleich(co2_g):
    """Gibt einen passenden Alltagsvergleich zurueck"""
    if co2_g <= 0:
        return ""
    auto_m  = round((co2_g / CO2_AUTO_PRO_KM) * 1000, 0)   # Meter Auto
    zug_m   = round((co2_g / CO2_ZUG_PRO_KM)  * 1000, 0)   # Meter Zug
    netflix = round((co2_g / CO2_NETFLIX_PRO_H) * 60, 1)    # Minuten Netflix

    if co2_g < 20:
        return str(int(auto_m)) + "m Autofahrt oder " + str(int(zug_m)) + "m Zugfahrt"
    elif co2_g < 100:
        return str(int(auto_m)) + "m Autofahrt oder " + str(netflix) + " Min. Netflix streamen"
    else:
        return str(round(auto_m/1000, 2)) + " km Autofahrt oder " + str(netflix) + " Min. Netflix streamen"


def berechne_impact(kat):
    co2  = CO2_PRO_KG.get(kat, 0) * GEWICHT_KG.get(kat, 0.1) * 1000
    geld = GEWICHT_KG.get(kat, 0.1) * KOSTEN_EUR_KG * 100 if kat not in ["Restmuell", "Sonderabfall"] else 0.0
    return round(co2, 1), round(geld, 1)

# ── Login ──────────────────────────────────────────────
NUTZER = {"Novares": {"passwort": "admin"}}

# ── Session State ──────────────────────────────────────
defaults = {
    "zaehler":          {k: 0 for k in KATEGORIEN},
    "letztes_ergebnis": None,
    "modus":            "foto",
    "eingeloggt":       False,
    "behaelter_id":     "",
    "nutzername":       "",
    "gesamt_co2":       0.0,
    "gesamt_cent":      0.0,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── ESP32 Bluetooth ────────────────────────────────────
def verbinde_esp32():
    for p in serial.tools.list_ports.comports():
        if "Novares" in p.description or "ESP32" in p.description or "SLAB" in p.description:
            try:
                return serial.Serial(p.device, 115200, timeout=2)
            except:
                pass
    return None

def sende_an_esp32(kategorie):
    bt = st.session_state.get("bt")
    if bt and bt.is_open:
        try:
            bt.write((kategorie + "\n").encode())
            return True
        except:
            st.session_state.bt = verbinde_esp32()
            return False
    return False

if "bt" not in st.session_state:
    st.session_state.bt = verbinde_esp32()


# ── Login Screen ───────────────────────────────────────
if not st.session_state.eingeloggt:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f0faf4; }
    #MainMenu, footer, header { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align:center;padding:40px 0 20px 0;">
        <div style="font-size:3.5rem;">&#9851;</div>
        <div style="font-size:2rem;font-weight:800;color:#1a5c2a;">NOVARES</div>
        <div style="font-size:0.9rem;color:#888;margin-top:4px;">Smart Recycling System</div>
    </div>
    """, unsafe_allow_html=True)
    with st.form("login_form"):
        nutzername = st.text_input("Benutzername", placeholder="z.B. Novares")
        passwort   = st.text_input("Passwort", type="password")
        behaelter  = st.selectbox("Behaelter-ID", ["NOV-001", "NOV-002", "NOV-003"])
        if st.form_submit_button("Anmelden", use_container_width=True):
            if nutzername in NUTZER and NUTZER[nutzername]["passwort"] == passwort:
                st.session_state.eingeloggt   = True
                st.session_state.nutzername   = nutzername
                st.session_state.behaelter_id = behaelter
                st.rerun()
            else:
                st.error("Benutzername oder Passwort falsch")
    st.stop()

# ── Keys ──────────────────────────────────────────────
GROQ_KEY  = st.secrets["GROQ_KEY"]
IMGBB_KEY = st.secrets["IMGBB_KEY"]
client    = Groq(api_key=GROQ_KEY)

# ── CSS ────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
* { font-family: 'Inter', sans-serif; }
.stApp { background-color: #f0faf4; }
.header {
    background: linear-gradient(135deg, #1a5c2a, #2e8b47);
    border-radius: 20px; padding: 24px 28px; margin-bottom: 24px;
    display: flex; align-items: center; gap: 18px;
}
.logo-text { color: white; font-size: 2.2rem; font-weight: 800; letter-spacing: -1px; margin: 0; }
.logo-sub  { color: #a8dbb8; font-size: 0.85rem; margin: 0; }
.logo-icon { font-size: 2.8rem; }
.result-box {
    border-radius: 20px; padding: 28px; text-align: center; margin-top: 20px;
    border: 2px solid rgba(0,0,0,0.06); background: white;
    box-shadow: 0 4px 24px rgba(0,0,0,0.06);
}
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────
col_head, col_logout = st.columns([5, 1])
with col_head:
    st.markdown(
        '<div class="header"><div class="logo-icon">&#9851;</div><div>'
        '<p class="logo-text">NOVARES</p>'
        '<p class="logo-sub">Smart Recycling &nbsp;|&nbsp; '
        + st.session_state.behaelter_id + ' &nbsp;|&nbsp; ' + st.session_state.nutzername
        + '</p></div></div>', unsafe_allow_html=True)
with col_logout:
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True):
        for k in defaults:
            st.session_state[k] = defaults[k]
        st.rerun()

# ── API ────────────────────────────────────────────────
def upload_bild(img_bytes):
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    r   = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_KEY, "image": b64})
    ans = r.json()
    if "data" not in ans:
        st.error("imgbb Fehler: " + str(ans)); st.stop()
    return ans["data"]["url"]

def analysiere_muell(img_url):
    prompt = """Du bist ein praeziser Recycling-Experte. Analysiere das Bild.

4 Behaelter + Sonderabfall:
PLASTIK: NUR reines Plastik (Flaschen, Tueten, Kunststoff) - NICHT Dosen, Tetrapak
PAPIER:  NUR reines Papier (Zeitung, Buecher, reine Pappe) - NICHT fettiger Karton, Tetrapak
BIO:     NUR kompostierbares (Obst, Gemuese, Kaffeesatz, Eierschalen) - NICHT Knochen
RESTMUELL: Metall, Dosen, Glas, Tetrapak, Verbundverpackungen, Windeln
SONDERABFALL: Batterien, Akkus, Elektronik, Medikamente, Farben, Lacke, Loesungsmittel

Antworte NUR so:
GEGENSTAND: [Beschreibung Deutsch]
MATERIAL: [genaues Material]
BEHAELTER: [Plastik, Papier, Bio, Restmuell oder Sonderabfall]
WARNUNG: [nur wenn Sonderabfall: warum gefaehrlich, sonst leer]
KOMPLEX: [JA oder NEIN]
SCHRITT1: [Trennschritt falls JA, sonst leer]
SCHRITT2: [weiterer Schritt, sonst leer]
SCHRITT3: [weiterer Schritt, sonst leer]"""

    r    = client.chat.completions.create(
        messages=[{"role": "user", "content": [
            {"type": "text",      "text": prompt},
            {"type": "image_url", "image_url": {"url": img_url}}
        ]}],
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        max_completion_tokens=250,
    )
    text = r.choices[0].message.content.strip()
    gegenstand, material, behaelter, warnung, komplex, schritte = "Unbekannt", "", "Restmuell", "", False, []
    for zeile in text.split("\n"):
        z = zeile.strip()
        if z.startswith("GEGENSTAND:"): gegenstand = z.replace("GEGENSTAND:", "").strip()
        elif z.startswith("MATERIAL:"):  material   = z.replace("MATERIAL:", "").strip()
        elif z.startswith("BEHAELTER:"):
            b = z.replace("BEHAELTER:", "").strip()
            behaelter = b if b in KATEGORIEN else MAPPING.get(b, "Restmuell")
        elif z.startswith("WARNUNG:"):   warnung  = z.replace("WARNUNG:", "").strip()
        elif z.startswith("KOMPLEX:"):   komplex  = "JA" in z.upper()
        elif z.startswith("SCHRITT1:"):
            s = z.replace("SCHRITT1:", "").strip()
            if s: schritte.append(s)
        elif z.startswith("SCHRITT2:"):
            s = z.replace("SCHRITT2:", "").strip()
            if s: schritte.append(s)
        elif z.startswith("SCHRITT3:"):
            s = z.replace("SCHRITT3:", "").strip()
            if s: schritte.append(s)
    if material and material.lower() not in gegenstand.lower():
        gegenstand = gegenstand + " (" + material + ")"
    return gegenstand, behaelter, warnung, komplex, schritte

def erstelle_qr_png(url):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a5c2a", back_color="white")
    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

# ── Modus-Schalter ─────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    if st.button("Foto-Modus", use_container_width=True,
                 type="primary" if st.session_state.modus == "foto" else "secondary"):
        st.session_state.modus = "foto"; st.rerun()
with c2:
    if st.button("Live-Modus", use_container_width=True,
                 type="primary" if st.session_state.modus == "live" else "secondary"):
        st.session_state.modus = "live"; st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ── Foto-Modus ─────────────────────────────────────────
if st.session_state.modus == "foto":
    st.markdown("### Halte einen Gegenstand in die Kamera")
    foto = st.camera_input("Kamera", label_visibility="collapsed")
    if foto:
        with st.spinner("KI analysiert..."):
            try:
                img = Image.open(foto)
                img.thumbnail((800, 800))
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=50)
                url = upload_bild(buf.getvalue())
                gegenstand, behaelter, warnung, komplex, schritte = analysiere_muell(url)
                co2_g, cent = berechne_impact(behaelter)
                st.session_state.zaehler[behaelter] += 1
                # ── ESP32 Motor ansteuern ──────────────
                if behaelter != "Sonderabfall":
                    sende_an_esp32(behaelter)
                st.session_state.gesamt_co2   += co2_g
                st.session_state.gesamt_cent  += cent
                st.session_state.letztes_ergebnis = {
                    "gegenstand": gegenstand, "kategorie": behaelter,
                    "warnung": warnung, "komplex": komplex, "schritte": schritte,
                    "fakt": random.choice(FAKTEN[behaelter]),
                    "co2_g": co2_g, "cent": cent,
                }
            except Exception as e:
                st.error("Fehler: " + str(e))

# ── Live-Modus ─────────────────────────────────────────
else:
    st.markdown("""
    <div style="background:#f5f5f5;border-radius:16px;padding:32px;text-align:center;border:2px dashed #ccc;">
        <div style="font-size:2.5rem;">&#128679;</div>
        <div style="font-size:1.1rem;font-weight:700;color:#555;margin:8px 0;">Live-Modus kommt bald</div>
        <div style="font-size:0.9rem;color:#888;">Wird aktiviert sobald der Muellbehaelter fertig gebaut ist.</div>
    </div>""", unsafe_allow_html=True)

# ── Ergebnis ───────────────────────────────────────────
if st.session_state.letztes_ergebnis:
    erg    = st.session_state.letztes_ergebnis
    kat    = erg["kategorie"]
    k      = KATEGORIEN[kat]
    farbe  = k["farbe"]

    # Ergebnis-Box
    st.markdown(
        '<div class="result-box" style="background:' + k["bg"] + ';border-color:' + farbe + '33;">'
        '<div style="font-size:1.1rem;color:#555;margin-bottom:6px;">Erkannt: <b>' + erg["gegenstand"] + '</b></div>'
        '<div style="font-size:2rem;font-weight:800;color:' + farbe + ';">' + kat + '</div>'
        '<div style="font-size:1rem;color:#777;margin-top:4px;">' + k["tonne"] + '</div>'
        '<div style="display:inline-block;padding:6px 18px;border-radius:100px;color:white;'
        'font-weight:700;font-size:0.85rem;margin-top:12px;background:' + farbe + ';">Erkannt</div>'
        '</div>', unsafe_allow_html=True)

    # Sonderabfall
    if kat == "Sonderabfall" or erg.get("warnung"):
        wtext = erg.get("warnung") or "Dieser Gegenstand gehoert zum Sonderabfall!"
        st.markdown(
            '<div style="background:#ffebee;border-left:5px solid #b71c1c;border-radius:12px;padding:16px 20px;margin-top:14px;">'
            '<div style="font-size:0.85rem;font-weight:700;color:#b71c1c;margin-bottom:6px;">ACHTUNG - SONDERABFALL</div>'
            '<div style="font-size:0.92rem;color:#333;">' + wtext + '</div>'
            '<div style="font-size:0.82rem;color:#888;margin-top:8px;">Zum naechsten Wertstoffhof bringen!</div>'
            '</div>', unsafe_allow_html=True)

    # Trennungsanleitung
    if erg.get("komplex") and erg.get("schritte"):
        teile = []
        for i, s in enumerate(erg["schritte"]):
            teile.append(
                '<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px;">'
                '<div style="background:' + farbe + ';color:white;border-radius:50%;width:24px;height:24px;'
                'min-width:24px;display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700;">'
                + str(i+1) + '</div>'
                '<div style="font-size:0.9rem;color:#333;padding-top:3px;">' + s + '</div></div>')
        st.markdown(
            '<div style="background:#fffde7;border-left:5px solid #f9a825;border-radius:12px;padding:16px 20px;margin-top:14px;">'
            '<div style="font-size:0.78rem;color:#888;font-weight:600;margin-bottom:10px;">TRENNUNGSANLEITUNG</div>'
            + "".join(teile) + '</div>', unsafe_allow_html=True)

    # Impact-Box
    co2_g = erg.get("co2_g", 0)
    cent  = erg.get("cent", 0)
    if co2_g > 0 or cent > 0:
        teile = []
        if co2_g > 0: teile.append("~" + str(co2_g) + "g CO2 gespart")
        if cent  > 0: teile.append("~" + str(cent)  + " Cent Entsorgungskosten vermieden")
        vergleich = co2_vergleich(co2_g)
        vergleich_html = ""
        if vergleich:
            vergleich_html = (
                '<div style="font-size:0.85rem;color:#555;margin-top:6px;">'
                '&#8776; Das entspricht: <b>' + vergleich + '</b></div>'
            )
        st.markdown(
            '<div style="background:#e8f5e9;border-left:5px solid #2e7d32;border-radius:12px;padding:14px 20px;margin-top:14px;">'
            '<div style="font-size:0.78rem;color:#888;font-weight:600;margin-bottom:6px;">DEIN IMPACT DIESER SCAN</div>'
            '<div style="font-size:0.95rem;color:#2e7d32;font-weight:700;">' + " &nbsp;|&nbsp; ".join(teile) + '</div>'
            + vergleich_html +
            '<div style="font-size:0.72rem;color:#aaa;margin-top:8px;">'
            'Quellen: Umweltbundesamt, DIW 2021, co2online.de, EVS Saar</div>'
            '</div>', unsafe_allow_html=True)

    # Recycling-Fakt
    st.markdown(
        '<div style="background:' + k["bg"] + ';border-left:5px solid ' + farbe + ';border-radius:12px;padding:16px 20px;margin-top:14px;">'
        '<div style="font-size:0.78rem;color:#888;margin-bottom:4px;font-weight:600;">WUSSTEST DU?</div>'
        '<div style="font-size:0.95rem;color:#333;line-height:1.5;">' + erg["fakt"] + '</div>'
        '</div>', unsafe_allow_html=True)

    # Korrektur
    st.markdown("<br>", unsafe_allow_html=True)
    kat_liste = list(KATEGORIEN.keys())
    neue_kat  = st.selectbox("Kategorie falsch? Hier korrigieren:", kat_liste, index=kat_liste.index(kat))
    if neue_kat != kat:
        if st.button("Korrektur bestaetigen"):
            st.session_state.zaehler[kat]     = max(0, st.session_state.zaehler[kat] - 1)
            st.session_state.zaehler[neue_kat]+= 1
            st.session_state.letztes_ergebnis["kategorie"] = neue_kat
            st.success("Korrigiert: " + kat + " zu " + neue_kat)
            st.rerun()

# ── Statistik ──────────────────────────────────────────
st.markdown("---")
st.markdown("### Heutige Statistik")

co2_heute  = round(st.session_state.gesamt_co2,  1)
cent_heute = round(st.session_state.gesamt_cent, 1)
if co2_heute > 0 or cent_heute > 0:
    st.markdown(
        '<div style="background:#e8f5e9;border-radius:14px;padding:16px 20px;margin-bottom:16px;'
        'display:flex;gap:32px;justify-content:center;flex-wrap:wrap;">'
        '<div style="text-align:center;">'
        '<div style="font-size:1.4rem;font-weight:800;color:#2e7d32;">' + str(co2_heute) + 'g</div>'
        '<div style="font-size:0.78rem;color:#888;">CO2 heute gespart</div></div>'
        '<div style="text-align:center;">'
        '<div style="font-size:1.4rem;font-weight:800;color:#1565c0;">' + str(cent_heute) + ' Ct</div>'
        '<div style="font-size:0.78rem;color:#888;">Entsorgungskosten vermieden</div></div>'
        '</div>', unsafe_allow_html=True)

kat_items = list(st.session_state.zaehler.items())
cols = st.columns(len(kat_items))
for i, (kat, anzahl) in enumerate(kat_items):
    farbe = KATEGORIEN[kat]["farbe"]
    with cols[i]:
        st.markdown(
            '<div style="background:white;border-radius:12px;padding:16px;text-align:center;'
            'border-top:4px solid ' + farbe + ';box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:12px;">'
            '<div style="font-size:1.6rem;font-weight:800;color:' + farbe + ';">' + str(anzahl) + '</div>'
            '<div style="font-size:0.72rem;color:#777;">' + kat + '</div>'
            '</div>', unsafe_allow_html=True)

if st.button("Statistik zuruecksetzen"):
    for k in defaults:
        st.session_state[k] = defaults[k]
    st.rerun()

# ── QR-Code ────────────────────────────────────────────
st.markdown("---")
st.markdown("### App teilen")
try:    APP_URL = st.context.url
except: APP_URL = "http://localhost:8501"

qr_png = erstelle_qr_png(APP_URL)
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    st.image(qr_png, use_container_width=True)
    st.download_button("QR-Code herunterladen", data=qr_png,
                       file_name="novares_qr.png", mime="image/png", use_container_width=True)
st.markdown('<p style="text-align:center;font-size:0.78rem;color:#aaa;">' + APP_URL + '</p>',
            unsafe_allow_html=True)
