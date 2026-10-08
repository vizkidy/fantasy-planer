import warnings
import unicodedata
import itertools
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import streamlit as st

warnings.filterwarnings("ignore")

def normalisiere(text):
    if not text:
        return ""
    ersetzungen = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "ø": "o", "æ": "ae", "đ": "d", "ł": "l"}
    t = text.lower()
    for alt, neu in ersetzungen.items():
        t = t.replace(alt, neu)
    norm = unicodedata.normalize('NFD', t)
    return "".join(c for c in norm if unicodedata.category(c) != 'Mn').replace("-", " ").strip()

def ermittle_update_tag():
    jetzt = datetime.now()
    if jetzt.hour < 23:
        stichtag = (jetzt - timedelta(days=1)).date()
    else:
        stichtag = jetzt.date()
    return str(stichtag)

@st.cache_data(ttl=86400)
def lade_marktwerte_taeglich(update_stichtag):
    url = "https://kickbased.de/kickbase-marktwerte/"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    res = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    daten = {}
    
    for row in soup.find_all("tr"):
        cols = [td.get_text().strip() for td in row.find_all(["td", "th"])]
        if len(cols) >= 4:
            name = cols[0]
            pos_raw = cols[2].lower()
            mw_str = cols[3].replace(".", "").replace("€", "").strip()
            
            pos = "MIT"
            if "tor" in pos_raw or "tw" in pos_raw:
                pos = "TW"
            elif "abw" in pos_raw or "def" in pos_raw:
                pos = "ABW"
            elif "sturm" in pos_raw or "ang" in pos_raw:
                pos = "ANG"
            elif "mit" in pos_raw:
                pos = "MIT"
                
            if mw_str.isdigit():
                daten[name] = {
                    "mw": int(mw_str),
                    "pos": pos,
                    "verein": cols[1],
                    "norm": normalisiere(name)
                }
    return daten

st.set_page_config(page_title="Fantasy Kader- & Bank-Planer", layout="wide")
st.title("⚽ Fantasy Kader- & Bank-Planer")

stichtag = ermittle_update_tag()
with st.spinner("Lade Tages-Marktwerte..."):
    alle_spieler = lade_marktwerte_taeglich(stichtag)

alle_namen = sorted(list(alle_spieler.keys()))

# Session States permanent absichern
if "reset_count" not in st.session_state:
    st.session_state.reset_count = 0

if "s11_spieler" not in st.session_state:
    st.session_state.s11_spieler = []

if "bank_spieler" not in st.session_state:
    st.session_state.bank_spieler = []

if "kontostand_speicher" not in st.session_state:
    st.session_state.kontostand_speicher = 0

# --- 1. SUCHE ---
col_such, col_btn_s11, col_btn_bank = st.columns([3.5, 1.2, 1.2])

with col_such:
    eingabe = st.text_input(
        label="Suche",
        placeholder="Spielername tippen (z. B. Kane, Diaz, Garcia, Olise)...",
        label_visibility="collapsed",
        key=f"search_bar_{st.session_state.reset_count}"
    )

such_norm = normalisiere(eingabe)

gefundene_spieler = []
if such_norm:
    prio1 = [n for n in alle_namen if any(part.startswith(such_norm) for part in alle_spieler[n]["norm"].split())]
    prio2 = [n for n in alle_namen if such_norm in alle_spieler[n]["norm"] and n not in prio1]
    gefundene_spieler = prio1 + prio2

ziel_spieler = None
if gefundene_spieler:
    ziel_spieler = gefundene_spieler[0]
    st.caption(f"🎯 Treffer: **{ziel_spieler}** ({alle_spieler[ziel_spieler]['pos']} | {alle_spieler[ziel_spieler]['verein']} | {alle_spieler[ziel_spieler]['mw']:,} €)")
elif such_norm:
    st.caption("*(Kein passender Spieler gefunden)*")

with col_btn_s11:
    if st.button("➕ Zu Start-11", use_container_width=True):
        if ziel_spieler:
            r_pos = alle_spieler[ziel_spieler]["pos"]
            aktuelle_tw = [n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "TW"]
            
            if r_pos == "TW" and len(aktuelle_tw) >= 1 and ziel_spieler not in st.session_state.s11_spieler:
                st.error(f"Maximal 1 Torwart erlaubt! Aktuell im Tor: {aktuelle_tw[0]}")
            elif len(st.session_state.s11_spieler) >= 11 and ziel_spieler not in st.session_state.s11_spieler:
                st.error("Start-11 ist mit 11 Spielern bereits voll!")
            elif ziel_spieler not in st.session_state.s11_spieler:
                st.session_state.s11_spieler.append(ziel_spieler)
                if ziel_spieler in st.session_state.bank_spieler:
                    st.session_state.bank_spieler.remove(ziel_spieler)
                st.session_state.reset_count += 1
                st.rerun()

with col_btn_bank:
    if st.button("➕ Zu Bank", use_container_width=True):
        if ziel_spieler:
            if ziel_spieler not in st.session_state.bank_spieler:
                st.session_state.bank_spieler.append(ziel_spieler)
                if ziel_spieler in st.session_state.s11_spieler:
                    st.session_state.s11_spieler.remove(ziel_spieler)
                st.session_state.reset_count += 1
                st.rerun()

st.divider()

# --- 2. TAKTIKBOARD & BANK BEREICH ---
col_board, col_bank = st.columns([2.5, 1.2])

with col_board:
    c_board_title, c_board_clear = st.columns([3, 1])
    with c_board_title:
        tw_list = [n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "TW"]
        abw_list = [n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "ABW"]
        mit_list = [n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "MIT"]
        ang_list = [n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "ANG"]
        st.subheader(f"📋 Taktikboard ({len(st.session_state.s11_spieler)}/11 Spieler — {len(abw_list)}-{len(mit_list)}-{len(ang_list)})")
    with c_board_clear:
        if st.session_state.s11_spieler:
            if st.button("🗑️ S11 leeren"):
                st.session_state.s11_spieler = []
                st.rerun()
    
    with st.container(border=True):
        def render_reihe(spieler_liste, titel):
            st.caption(f"**{titel}** ({len(spieler_liste)})")
            if not spieler_liste:
                st.write("*(Kein Spieler)*")
                return
            cols = st.columns(max(len(spieler_liste), 1))
            for idx, name in enumerate(spieler_liste):
                mw = alle_spieler[name]["mw"]
                with cols[idx]:
                    with st.container(border=True):
                        st.markdown(f"**{name}**")
                        st.caption(f"{mw:,} €")
                        b_del, b_move = st.columns(2)
                        with b_del:
                            if st.button("✕", key=f"del_board_{name}", help="Entfernen"):
                                st.session_state.s11_spieler.remove(name)
                                st.rerun()
                        with b_move:
                            if st.button("➡️", key=f"to_bank_{name}", help="Auf die Bank verschieben"):
                                st.session_state.s11_spieler.remove(name)
                                if name not in st.session_state.bank_spieler:
                                    st.session_state.bank_spieler.append(name)
                                st.rerun()

        render_reihe(ang_list, "ANGRIFF (STURM)")
        st.markdown("---")
        render_reihe(mit_list, "MITTELFELD")
        st.markdown("---")
        render_reihe(abw_list, "ABWEHR")
        st.markdown("---")
        render_reihe(tw_list, "TORWART")

with col_bank:
    c_bank_title, c_bank_clear = st.columns([3, 1])
    with c_bank_title:
        st.subheader(f"🪑 Bank ({len(st.session_state.bank_spieler)})")
    with c_bank_clear:
        if st.session_state.bank_spieler:
            if st.button("🗑️ Bank leeren"):
                st.session_state.bank_spieler = []
                st.rerun()
        
    if not st.session_state.bank_spieler:
        st.info("Noch keine Bank-Spieler hinzugefügt.")
    for name in st.session_state.bank_spieler:
        mw = alle_spieler[name]["mw"]
        pos = alle_spieler[name]["pos"]
        with st.container(border=True):
            c_txt, c_up, c_del = st.columns([3, 1, 1])
            with c_txt:
                st.markdown(f"**{name}**")
                st.caption(f"{pos} | {mw:,} €")
            with c_up:
                if st.button("⬅️", key=f"to_s11_{name}", help="In die Start-11 verschieben"):
                    aktuelle_tw = [n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "TW"]
                    if pos == "TW" and len(aktuelle_tw) >= 1:
                        st.error(f"Bereits ein Torwart vorhanden ({aktuelle_tw[0]})!")
                    elif len(st.session_state.s11_spieler) >= 11:
                        st.error("Start-11 ist bereits voll (11 Spieler)!")
                    else:
                        st.session_state.bank_spieler.remove(name)
                        st.session_state.s11_spieler.append(name)
                        st.rerun()
            with c_del:
                if st.button("✕", key=f"del_bank_{name}", help="Spieler ganz entfernen"):
                    st.session_state.bank_spieler.remove(name)
                    st.rerun()

st.divider()

# --- 3. BERECHNUNG & KONTOSTAND-SPEICHER ---
st.subheader("💰 Kontostand & Minus-Ausgleich")

def aktualisiere_kontostand():
    st.session_state.kontostand_speicher = st.session_state.konto_input_widget

kontostand = st.number_input(
    "Aktueller Kontostand (€):",
    value=st.session_state.kontostand_speicher,
    step=500000,
    format="%d",
    key="konto_input_widget",
    on_change=aktualisiere_kontostand
)
st.session_state.kontostand_speicher = kontostand

bank_dict = {name: alle_spieler[name]["mw"] for name in st.session_state.bank_spieler}
s11_dict = {name: alle_spieler[name]["mw"] for name in st.session_state.s11_spieler}
summe_bank_gesamt = sum(bank_dict.values())

m1, m2 = st.columns(2)
m1.metric("Aktueller Kontostand", f"{kontostand:,} €")
m2.metric("Gesamtwert aller Bank-Spieler", f"{summe_bank_gesamt:,} €", help="Kapitalreserve auf der Bank")

if kontostand >= 0:
    st.success(f"🎉 Dein Konto ist mit **+{kontostand:,} €** im Plus! Du musst niemanden verkaufen und kannst **alle {len(st.session_state.bank_spieler)} Spieler auf der Bank behalten**.")
elif kontostand + summe_bank_gesamt >= 0:
    fehlbetrag = abs(kontostand)
    st.info(f"Du bist mit **{fehlbetrag:,} €** im Minus. Dein Bankwert reicht aus, ohne die Start-11 anzugreifen!")
    st.markdown("#### Verkaufsoptionen von der Bank:")
    
    optionen_bank = []
    for r in range(1, len(bank_dict) + 1):
        for kombi in itertools.combinations(bank_dict.items(), r):
            summe_verkauf = sum(mw for _, mw in kombi)
            if summe_verkauf >= fehlbetrag:
                ueber = summe_verkauf - fehlbetrag
                verkaufte = {n for n, _ in kombi}
                behalten = [n for n in st.session_state.bank_spieler if n not in verkaufte]
                optionen_bank.append((kombi, summe_verkauf, ueber, behalten))
                
    optionen_bank.sort(key=lambda x: (len(x[0]), x[2]))
    
    for idx, (kombi, summe, restplus, behalten) in enumerate(optionen_bank[:5], 1):
        v_text = ", ".join([f"{n} ({alle_spieler[n]['pos']}, {mw:,} €)" for n, mw in kombi])
        b_text = ", ".join([f"{n} ({alle_spieler[n]['pos']})" for n in behalten]) if behalten else "*(Keine - alle Bankspieler verkauft)*"
        
        with st.expander(f"Option {idx}: Nur {len(kombi)} Bankspieler verkaufen — Erlös: +{summe:,} € | Behalten: {len(behalten)} Spieler"):
            st.write(f"💸 **Verkaufen:** {v_text}")
            st.write(f"🛡️ **Auf der Bank behalten:** {b_text}")
            st.success(f"**Neuer Kontostand:** +{restplus:,} €")
else:
    fehlbetrag_nach_bank = abs(kontostand + summe_bank_gesamt)
    st.warning(f"Selbst der Verkauf der gesamten Bank lässt ein Rest-Minus von **{fehlbetrag_nach_bank:,} €** übrig. Deine Start-11 muss einbezogen werden.")
    
    if not s11_dict:
        st.info("Füge Spieler zu deiner Start-11 hinzu, um Verkaufsoptionen zu berechnen.")
    else:
        st.markdown("#### Optimale Verkaufsoptionen aus der Start-11:")
        gueltige_s11_optionen = []
        
        for r in range(1, len(s11_dict) + 1):
            for kombi in itertools.combinations(s11_dict.items(), r):
                summe_verkauf = sum(mw for _, mw in kombi)
                if summe_verkauf >= fehlbetrag_nach_bank:
                    verkaufte_namen = {name for name, _ in kombi}
                    rest_kader = [n for n in st.session_state.s11_spieler if n not in verkaufte_namen]
                    
                    fehlende_linien = []
                    if not any(alle_spieler[n]["pos"] == "TW" for n in rest_kader):
                        fehlende_linien.append("TW")
                    if not any(alle_spieler[n]["pos"] == "ABW" for n in rest_kader):
                        fehlende_linien.append("ABW")
                    if not any(alle_spieler[n]["pos"] == "MIT" for n in rest_kader):
                        fehlende_linien.append("MIT")
                    if not any(alle_spieler[n]["pos"] == "ANG" for n in rest_kader):
                        fehlende_linien.append("ANG")
                    
                    ueberschuss = summe_verkauf - fehlbetrag_nach_bank
                    gueltige_s11_optionen.append((kombi, summe_verkauf, ueberschuss, fehlende_linien))
        
        gueltige_s11_optionen.sort(key=lambda x: (len(x[3]), len(x[0]), x[2]))
        
        if gueltige_s11_optionen:
            for idx, (kombi, summe, restplus, leer) in enumerate(gueltige_s11_optionen[:6], 1):
                details = ", ".join([f"{n} ({alle_spieler[n]['pos']}, {mw:,} €)" for n, mw in kombi])
                titel = f"Option {idx}: Alle Bankspieler + {len(kombi)} S11-Spieler abgeben — Erlös: +{summe + summe_bank_gesamt:,} €"
                if leer:
                    titel += f" ⚠️ (Lücke auf: {', '.join(leer)})"
                    
                with st.expander(titel):
                    st.write(f"💸 **Aus der Start-11 verkaufen:** {details} *(sowie die gesamte Bank)*")
                    st.success(f"**Neuer Kontostand:** +{restplus:,} €")
                    if leer:
                        st.caption(f"💡 Hinweis: Nach dem Verkauf fehlt dir ein Spieler auf {', '.join(leer)}.")
        else:
            st.error("Selbst Bank + Start-11 reichen nicht aus, um das Minus zu decken!")

# --- 4. FOOTER ---
st.divider()
st.caption("Hinweis: Privates Fan- und Hilfsprojekt. Dieses Tool steht in keiner offiziellen Verbindung zu Kickbase oder der Kickbase GmbH. Alle Markennamen und Daten dienen lediglich informativen Zwecken.")
