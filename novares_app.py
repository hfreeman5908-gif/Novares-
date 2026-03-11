import streamlit as st
import base64
import requests
from groq import Groq
from PIL import Image
import io
import random
import qrcode

# ── Seiten-Config ──────────────────────────────────────
st.set_page_config(page_title="Novares | Smart Recycling", page_icon="♻", layout="centered")

# ── 4 Behaelter + Sonderabfall ─────────────────────────
KATEGORIEN = {
    "Plastik":      {"farbe": "#e65c00", "tonne": "Behaelter 1 - Nur Plastik",         "bg": "#fff3e0"},
    "Papier":       {"farbe": "#1565c0", "tonne": "Behaelter 2 - Nur Papier",           "bg": "#e3f2fd"},
    "Bio":          {"farbe": "#6d4c41", "tonne": "Behaelter 3 - Nur Kompostierbares",  "bg": "#efebe9"},
    "Restmuell":    {"farbe": "#37474f", "tonne": "Behaelter 4 - Restmuell",            "bg": "#f5f5f5"},
    "Sonderabfall": {"farbe": "#b71c1c", "tonne": "Sonderabfall - Nicht in den Muell!", "bg": "#ffebee"},
}

MAPPING = {
    "Plastik":      "Plastik",
    "Metall":       "Restmuell",
    "Glas":         "Restmuell",
    "Wertstoffe":   "Plastik",
    "Papier":       "Papier",
    "Karton":       "Restmuell",
    "Pappe":        "Papier",
    "Bio":          "Bio",
    "Biom\u00fcll": "Bio",
    "Biomuell":     "Bio",
    "Restm\u00fcll":"Restmuell",
    "Restmuell":    "Restmuell",
    "Sonderabfall": "Sonderabfall",
}

FAKTEN = {
    "Plastik": [
        "Jedes Jahr landen 8 Millionen Tonnen Plastik im Meer.",
        "Aus 25 PET-Flaschen kann ein Fleece-Pullover hergestellt werden.",
        "Eine Plastikflasche braucht bis zu 450 Jahre um sich zu zersetzen.",
        "Recyceltes Plastik spart bis zu 80% Energie gegenueber Neuproduktion.",
        "Nur reines Plastik gehoert hier rein - gemischte Verpackungen in Restmuell.",
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
        "Kompostierung reduziert Methan-Emissionen aus Deponien erheblich.",
    ],
    "Restmuell": [
        "Restmuell wird in Deutschland meist thermisch verwertet - also verbrannt.",
        "Je weniger Restmuell, desto besser fuer die Umweltbilanz.",
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


# ── Impact-Daten (belegte Quellen) ────────────────────
# CO2: DIW 2021, Umweltbundesamt, Wien Biotonnen-Studie
# Kosten: AWB Koeln, Stadtreinigung Hamburg (Restmuell ~0.44 EUR/kg)
#         Recycling ist fuer den Verbraucher kostenlos (Duales System)

CO2_PRO_KG = {
    "Plastik":      1.5,    # DIW 2021: konservativ 1.5 kg CO2/kg gespart
    "Papier":       0.15,   # UBA 2023: ~15% CO2-Einsparung bei Papier
    "Bio":          0.1,    # Wien: 9.000t CO2 / ~90.000t Bioabfall
    "Restmuell":    0.0,
    "Sonderabfall": 0.0,
}

GEWICHT_KG = {
    "Plastik":      0.05,   # ~50g Durchschnitt (Flasche 17g, Tuete 10g etc.)
    "Papier":       0.1,    # ~100g (Zeitung, Karton)
    "Bio":          0.15,   # ~150g (Apfel, Gemueseabfall)
    "Restmuell":    0.1,
    "Sonderabfall": 0.05,
}

# Restmuell kostet ~0.44 EUR/kg (EVS Saar Verwiegesystem, repraesentativ)
# Recycling kostet den Verbraucher 0 EUR (finanziert durch Duales System)
KOSTEN_RESTMUELL_PRO_KG = 0.44

def berechne_impact(kategorie):
    co2 = CO2_PRO_KG.get(kategorie, 0) * GEWICHT_KG.get(kategorie, 0.1) * 1000  # in Gramm
    geld = GEWICHT_KG.get(kategorie, 0.1) * KOSTEN_RESTMUELL_PRO_KG if kategorie not in ["Restmuell","Sonderabfall"] else 0.0
    return round(co2, 1), round(geld * 100, 1)  # CO2 in Gramm, Geld in Cent

# ── Fake Login ─────────────────────────────────────────
NUTZER = {
    "Novares": {"passwort": "admin", "behaelter": ["NOV-001", "NOV-002", "NOV-003"]},
}

# ── Session State ──────────────────────────────────────
if "zaehler" not in st.session_state:
    st.session_state.zaehler = {k: 0 for k in KATEGORIEN}
if "letztes_ergebnis" not in st.session_state:
    st.session_state.letztes_ergebnis = None
if "modus" not in st.session_state:
    st.session_state.modus = "foto"
if "eingeloggt" not in st.session_state:
    st.session_state.eingeloggt = False
if "behaelter_id" not in st.session_state:
    st.session_state.behaelter_id = ""
if "nutzername" not in st.session_state:
    st.session_state.nutzername = ""

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
        <div style="font-size:2rem;font-weight:800;color:#1a5c2a;letter-spacing:-1px;">NOVARES</div>
        <div style="font-size:0.9rem;color:#888;margin-top:4px;">Smart Recycling System</div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        nutzername = st.text_input("Benutzername", placeholder="z.B. Novares")
        passwort   = st.text_input("Passwort", type="password", placeholder="...")
        behaelter  = st.selectbox("Behaelter-ID (steht am Eimer)", ["NOV-001", "NOV-002", "NOV-003"])
        login_btn  = st.form_submit_button("Anmelden", use_container_width=True)

        if login_btn:
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
client = Groq(api_key=GROQ_KEY)

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
.obj-name  { font-size: 1.1rem; color: #555; margin-bottom: 6px; }
.kategorie { font-size: 2rem; font-weight: 800; margin: 8px 0; }
.tonne     { font-size: 1rem; color: #777; margin-top: 4px; }
.badge     { display: inline-block; padding: 6px 18px; border-radius: 100px;
              color: white; font-weight: 700; font-size: 0.85rem; margin-top: 12px; }
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Header + Logout ────────────────────────────────────
col_head, col_logout = st.columns([5, 1])
with col_head:
    st.markdown(
        '<div class="header">'
        '<div class="logo-icon">&#9851;</div>'
        '<div>'
        '<p class="logo-text">NOVARES</p>'
        '<p class="logo-sub">Smart Recycling &nbsp;|&nbsp; '
        + st.session_state.behaelter_id + ' &nbsp;|&nbsp; ' + st.session_state.nutzername +
        '</p></div></div>',
        unsafe_allow_html=True
    )
with col_logout:
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True):
        for key in ["eingeloggt","nutzername","behaelter_id","letztes_ergebnis"]:
            st.session_state[key] = False if key == "eingeloggt" else ""
        st.session_state.letztes_ergebnis = None
        st.rerun()

# ── API Funktionen ─────────────────────────────────────
def upload_bild(img_bytes):
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_KEY, "image": b64})
    antwort = r.json()
    if "data" not in antwort:
        st.error("imgbb Fehler: " + str(antwort))
        st.stop()
    return antwort["data"]["url"]

def analysiere_muell(img_url):
    prompt = """Du bist ein praeziser Recycling-Experte fuer Deutschland. Analysiere das Bild genau.

Es gibt genau 4 Behaelter und Sonderabfall:

PLASTIK: NUR reines Plastik (PET-Flaschen, Plastiktueten, Kunststoff)
  NICHT: Dosen, Metall, Tetrapak, beschichtetes Papier

PAPIER: NUR reines Papier (Zeitungen, Buecher, reine Pappe)
  NICHT: Tetrapak, fettiger Pizzakarton, Papier-Plastik-Verbund

BIO: NUR kompostierbares (Essensreste, Obst, Gemuese, Kaffeesatz, Eierschalen, Pflanzen)
  NICHT: Fleischknochen, behandeltes Holz, Zigaretten

RESTMUELL: Metall, Dosen, Glas, Verbundverpackungen, Tetrapak, Windeln, Styropor

SONDERABFALL - NIEMALS in normalen Muell:
  Batterien, Akkus, Elektronik, Medikamente, Farben, Lacke, Loesungsmittel,
  Spraydosen unter Druck, Leuchtstoffroehren, Thermometer, Motoroel

Antworte NUR in diesem Format:
GEGENSTAND: [kurze Beschreibung auf Deutsch]
MATERIAL: [genaues Material]
BEHAELTER: [eines von: Plastik, Papier, Bio, Restmuell, Sonderabfall]
WARNUNG: [nur wenn Sonderabfall: warum gefaehrlich, sonst leer lassen]
KOMPLEX: [JA wenn Trennung noetig, sonst NEIN]
SCHRITT1: [Trennungsschritt falls KOMPLEX=JA, sonst leer lassen]
SCHRITT2: [weiterer Schritt falls vorhanden, sonst leer lassen]
SCHRITT3: [weiterer Schritt falls vorhanden, sonst leer lassen]"""

    r = client.chat.completions.create(
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": img_url}}
        ]}],
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        max_completion_tokens=250,
    )
    text = r.choices[0].message.content.strip()
    gegenstand, material, behaelter, warnung, komplex, schritte = "Unbekannt", "", "Restmuell", "", False, []
    for zeile in text.split("\n"):
        zeile = zeile.strip()
        if zeile.startswith("GEGENSTAND:"):
            gegenstand = zeile.replace("GEGENSTAND:", "").strip()
        elif zeile.startswith("MATERIAL:"):
            material = zeile.replace("MATERIAL:", "").strip()
        elif zeile.startswith("BEHAELTER:"):
            b = zeile.replace("BEHAELTER:", "").strip()
            if b in KATEGORIEN:
                behaelter = b
            else:
                behaelter = MAPPING.get(b, "Restmuell")
        elif zeile.startswith("WARNUNG:"):
            warnung = zeile.replace("WARNUNG:", "").strip()
        elif zeile.startswith("KOMPLEX:"):
            komplex = "JA" in zeile.upper()
        elif zeile.startswith("SCHRITT1:"):
            s = zeile.replace("SCHRITT1:", "").strip()
            if s: schritte.append(s)
        elif zeile.startswith("SCHRITT2:"):
            s = zeile.replace("SCHRITT2:", "").strip()
            if s: schritte.append(s)
        elif zeile.startswith("SCHRITT3:"):
            s = zeile.replace("SCHRITT3:", "").strip()
            if s: schritte.append(s)
    if material and material.lower() not in gegenstand.lower():
        gegenstand = gegenstand + " (" + material + ")"
    return gegenstand, behaelter, warnung, komplex, schritte

def erstelle_qr_png(url):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a5c2a", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ── Modus-Schalter ─────────────────────────────────────
col_l, col_r = st.columns(2)
with col_l:
    if st.button("Foto-Modus", use_container_width=True,
                 type="primary" if st.session_state.modus == "foto" else "secondary"):
        st.session_state.modus = "foto"
        st.rerun()
with col_r:
    if st.button("Live-Modus", use_container_width=True,
                 type="primary" if st.session_state.modus == "live" else "secondary"):
        st.session_state.modus = "live"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ── FOTO-MODUS ─────────────────────────────────────────
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
                st.session_state.zaehler[behaelter] += 1
                co2_g, cent = berechne_impact(behaelter)
                if "gesamt_co2" not in st.session_state:
                    st.session_state.gesamt_co2  = 0.0
                    st.session_state.gesamt_cent = 0.0
                st.session_state.gesamt_co2  += co2_g
                st.session_state.gesamt_cent += cent
                st.session_state.letztes_ergebnis = {
                    "gegenstand": gegenstand,
                    "kategorie":  behaelter,
                    "warnung":    warnung,
                    "komplex":    komplex,
                    "schritte":   schritte,
                    "fakt":       random.choice(FAKTEN[behaelter]),
                }
            except Exception as e:
                st.error("Fehler: " + str(e))

# ── LIVE-MODUS ─────────────────────────────────────────
else:
    st.markdown("""
    <div style="background:#f5f5f5;border-radius:16px;padding:32px;text-align:center;
                border:2px dashed #ccc;margin-top:8px;">
        <div style="font-size:2.5rem;margin-bottom:12px;">&#128679;</div>
        <div style="font-size:1.1rem;font-weight:700;color:#555;margin-bottom:8px;">
            Live-Modus kommt bald
        </div>
        <div style="font-size:0.9rem;color:#888;">
            Wird aktiviert sobald der Muellbehaelter fertig gebaut ist.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Ergebnis anzeigen ──────────────────────────────────
if st.session_state.letztes_ergebnis:
    erg     = st.session_state.letztes_ergebnis
    akt_kat = erg["kategorie"]
    k       = KATEGORIEN[akt_kat]
    farbe   = k["farbe"]

    st.markdown(
        '<div class="result-box" style="background:' + k["bg"] + ';border-color:' + farbe + '33;">'
        '<div class="obj-name">Erkannt: <b>' + erg["gegenstand"] + '</b></div>'
        '<div class="kategorie" style="color:' + farbe + ';">' + akt_kat + '</div>'
        '<div class="tonne">' + k["tonne"] + '</div>'
        '<div class="badge" style="background:' + farbe + ';">Erkannt</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Sonderabfall-Warnung
    if akt_kat == "Sonderabfall" or erg.get("warnung"):
        warn_text = erg.get("warnung") or "Dieser Gegenstand gehoert zum Sonderabfall!"
        st.markdown(
            '<div style="background:#ffebee;border-left:5px solid #b71c1c;'
            'border-radius:12px;padding:16px 20px;margin-top:14px;">'
            '<div style="font-size:0.85rem;font-weight:700;color:#b71c1c;margin-bottom:6px;">'
            'ACHTUNG - SONDERABFALL</div>'
            '<div style="font-size:0.92rem;color:#333;">' + warn_text + '</div>'
            '<div style="font-size:0.82rem;color:#888;margin-top:8px;">'
            'Zum naechsten Wertstoffhof bringen!</div>'
            '</div>',
            unsafe_allow_html=True
        )

    # Trennungsanleitung
    if erg.get("komplex") and erg.get("schritte"):
        teile = []
        for i, s in enumerate(erg["schritte"]):
            teile.append(
                '<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px;">'
                '<div style="background:' + farbe + ';color:white;border-radius:50%;'
                'width:24px;height:24px;min-width:24px;display:flex;align-items:center;'
                'justify-content:center;font-size:0.75rem;font-weight:700;">' + str(i+1) + '</div>'
                '<div style="font-size:0.9rem;color:#333;padding-top:3px;">' + s + '</div>'
                '</div>'
            )
        st.markdown(
            '<div style="background:#fffde7;border-left:5px solid #f9a825;'
            'border-radius:12px;padding:16px 20px;margin-top:14px;">'
            '<div style="font-size:0.78rem;color:#888;font-weight:600;margin-bottom:10px;">'
            'TRENNUNGSANLEITUNG</div>' + "".join(teile) + '</div>',
            unsafe_allow_html=True
        )

    # Recycling-Fakt
    st.markdown(
        '<div style="background:' + k["bg"] + ';border-left:5px solid ' + farbe + ';'
        'border-radius:12px;padding:16px 20px;margin-top:14px;">'
        '<div style="font-size:0.78rem;color:#888;margin-bottom:4px;font-weight:600;">WUSSTEST DU?</div>'
        '<div style="font-size:0.95rem;color:#333;line-height:1.5;">' + erg["fakt"] + '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Impact-Box
    co2_g, cent = berechne_impact(akt_kat)
    if co2_g > 0 or cent > 0:
        co2_text  = ("~" + str(co2_g) + "g CO2 gespart") if co2_g > 0 else ""
        geld_text = ("~" + str(cent) + " Cent Entsorgungskosten vermieden") if cent > 0 else ""
        beide     = " &nbsp;|&nbsp; ".join(filter(None, [co2_text, geld_text]))
        st.markdown(
            '<div style="background:#e8f5e9;border-left:5px solid #2e7d32;'
            'border-radius:12px;padding:14px 20px;margin-top:14px;">'
            '<div style="font-size:0.78rem;color:#888;font-weight:600;margin-bottom:6px;">DEIN IMPACT</div>'
            '<div style="font-size:0.95rem;color:#2e7d32;font-weight:700;">' + beide + '</div>'
            '<div style="font-size:0.72rem;color:#aaa;margin-top:6px;">'
            'Schaetzung basierend auf: Umweltbundesamt, DIW 2021, EVS Saar Entsorgungsgebuehren</div>'
            '</div>',
            unsafe_allow_html=True
        )

    # Tages-Impact in Session State akkumulieren
    if "gesamt_co2" not in st.session_state:
        st.session_state.gesamt_co2  = 0.0
        st.session_state.gesamt_cent = 0.0

    # Korrektur
    st.markdown("<br>", unsafe_allow_html=True)
    kat_liste = list(KATEGORIEN.keys())
    neue_kat  = st.selectbox("Kategorie falsch? Hier korrigieren:", kat_liste,
                              index=kat_liste.index(akt_kat))
    if neue_kat != akt_kat:
        if st.button("Korrektur bestaetigen"):
            st.session_state.zaehler[akt_kat] = max(0, st.session_state.zaehler[akt_kat] - 1)
            st.session_state.zaehler[neue_kat] += 1
            st.session_state.letztes_ergebnis["kategorie"] = neue_kat
            st.success("Korrigiert: " + akt_kat + " zu " + neue_kat)
            st.rerun()

# ── Statistik ──────────────────────────────────────────
st.markdown("---")
st.markdown("### Heutige Statistik")
kat_items = list(st.session_state.zaehler.items())
cols = st.columns(len(kat_items))
for i, (kat, anzahl) in enumerate(kat_items):
    farbe = KATEGORIEN[kat]["farbe"]
    with cols[i]:
        st.markdown(
            '<div style="background:white;border-radius:12px;padding:16px;text-align:center;'
            'border-top:4px solid ' + farbe + ';box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:12px;">'
            '<div style="font-size:1.6rem;font-weight:800;color:' + farbe + ';">' + str(anzahl) + '</div>'
            '<div style="font-size:0.75rem;color:#777;">' + kat + '</div>'
            '</div>',
            unsafe_allow_html=True
        )

if st.button("Statistik zuruecksetzen"):
    st.session_state.zaehler      = {k: 0 for k in KATEGORIEN}
    st.session_state.letztes_ergebnis = None
    st.session_state.gesamt_co2   = 0.0
    st.session_state.gesamt_cent  = 0.0
    st.rerun()

# ── QR-Code ────────────────────────────────────────────
st.markdown("---")
st.markdown("### App teilen")

try:
    APP_URL = st.context.url
except Exception:
    APP_URL = "http://localhost:8501"

qr_png = erstelle_qr_png(APP_URL)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image(qr_png, use_container_width=True)
    st.download_button("QR-Code herunterladen", data=qr_png,
                       file_name="novares_qr.png", mime="image/png", use_container_width=True)
st.markdown(
    '<p style="text-align:center;font-size:0.78rem;color:#aaa;margin-top:8px;">' + APP_URL + '</p>',
    unsafe_allow_html=True
)
