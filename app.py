from datetime import datetime, timedelta
import itertools
import unicodedata
import warnings
from bs4 import BeautifulSoup
import requests
import streamlit as st

warnings.filterwarnings("ignore")


def bereinige_text(text):
  if not text:
    return ""
  norm = unicodedata.normalize("NFD", text)
  clean = "".join(c for c in norm if unicodedata.category(c) != "Mn")
  return clean.lower().replace("-", " ").strip()


def ermittle_update_tag():
  """Liefert den Stichtag für das 23:00-Uhr-Update.

  Vor 23:00 Uhr gilt der Vortag, ab 23:00 Uhr der aktuelle Tag.
  """
  jetzt = datetime.now()
  if jetzt.hour < 23:
    stichtag = (jetzt - timedelta(days=1)).date()
  else:
    stichtag = jetzt.date()
  return str(stichtag)


@st.cache_data(ttl=86400)
def lade_marktwerte_taeglich(update_stichtag):
  """Wird genau 1x täglich ab 23:00 Uhr neu ausgeführt."""
  url = "https://kickbased.de/kickbase-marktwerte/"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
      )
  }
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
            "clean_name": bereinige_text(name),
        }
  return daten


# Webseiten-Setup mit neutralem Namen
st.set_page_config(page_title="Fantasy Kader- & Bank-Planer", layout="wide")
st.title("⚽ Fantasy Kader- & Bank-Planer")
st.caption(
    "Tägliche Marktwert-Aktualisierung um 23:00 Uhr | Optimale"
    " Verkaufskombinationen"
)

# Daten laden basierend auf dem 23:00-Uhr-Stichtag
stichtag = ermittle_update_tag()
with st.spinner("Lade Tages-Marktwerte..."):
  alle_spieler = lade_marktwerte_taeglich(stichtag)

alle_namen = sorted(list(alle_spieler.keys()))


def match_spieler(suchbegriff):
  such_clean = bereinige_text(suchbegriff)
  for name, info in alle_spieler.items():
    if such_clean in info["clean_name"]:
      return name
  return None


# Session States
if "search_reset_id" not in st.session_state:
  st.session_state.search_reset_id = 0

if "s11_spieler" not in st.session_state:
  standard_s11 = [
      "Moritz Nicolas",
      "Coufal",
      "Orban",
      "Simpson",
      "Garcia",
      "Stiller",
      "Nwaneri",
      "Leweling",
      "Luis Diaz",
      "Schick",
      "Nkunku",
  ]
  st.session_state.s11_spieler = [
      match_spieler(s) for s in standard_s11 if match_spieler(s)
  ]

if "bank_spieler" not in st.session_state:
  standard_bank = ["Curda", "Wojcik", "Arrhov", "Nadir", "Ulrich"]
  st.session_state.bank_spieler = [
      match_spieler(s) for s in standard_bank if match_spieler(s)
  ]

# --- 1. SUCHE MIT AUTO-RESET ---
st.markdown("### Spieler suchen & zuweisen")
col_such, col_btn_s11, col_btn_bank = st.columns([3.5, 1.2, 1.2])

with col_such:
  ausgewaehlt = st.selectbox(
      label="Suche",
      options=[""]
      + [
          f"{n} ({alle_spieler[n]['pos']} | {alle_spieler[n]['verein']} |"
          f" {alle_spieler[n]['mw']:,} €)"
          for n in alle_namen
      ],
      index=0,
      label_visibility="collapsed",
      key=f"search_select_{st.session_state.search_reset_id}",
  )

with col_btn_s11:
  if st.button("➕ Zu Start-11", use_container_width=True):
    if ausgewaehlt:
      r_name = ausgewaehlt.split(" (")[0]
      r_pos = alle_spieler[r_name]["pos"]

      aktuelle_tw = [
          n
          for n in st.session_state.s11_spieler
          if alle_spieler[n]["pos"] == "TW"
      ]
      if (
          r_pos == "TW"
          and len(aktuelle_tw) >= 1
          and r_name not in st.session_state.s11_spieler
      ):
        st.error(f"Maximal 1 Torwart erlaubt! Aktuell im Tor: {aktuelle_tw[0]}")
      elif (
          len(st.session_state.s11_spieler) >= 11
          and r_name not in st.session_state.s11_spieler
      ):
        st.error("Start-11 ist mit 11 Spielern bereits voll!")
      elif r_name not in st.session_state.s11_spieler:
        st.session_state.s11_spieler.append(r_name)
        if r_name in st.session_state.bank_spieler:
          st.session_state.bank_spieler.remove(r_name)
        st.session_state.search_reset_id += 1
        st.rerun()

with col_btn_bank:
  if st.button("➕ Zu Bank", use_container_width=True):
    if ausgewaehlt:
      r_name = ausgewaehlt.split(" (")[0]
      if r_name not in st.session_state.bank_spieler:
        st.session_state.bank_spieler.append(r_name)
        if r_name in st.session_state.s11_spieler:
          st.session_state.s11_spieler.remove(r_name)
        st.session_state.search_reset_id += 1
        st.rerun()

st.divider()

# --- 2. TAKTIKBOARD & BANK BEREICH ---
col_board, col_bank = st.columns([2.5, 1.2])

with col_board:
  tw_list = [
      n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "TW"
  ]
  abw_list = [
      n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "ABW"
  ]
  mit_list = [
      n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "MIT"
  ]
  ang_list = [
      n for n in st.session_state.s11_spieler if alle_spieler[n]["pos"] == "ANG"
  ]

  st.subheader(
      f"📋 Taktikboard ({len(st.session_state.s11_spieler)}/11 Spieler — Formation"
      f" {len(abw_list)}-{len(mit_list)}-{len(ang_list)})"
  )

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
              if st.button(
                  "➡️",
                  key=f"to_bank_{name}",
                  help="Auf die Bank verschieben",
              ):
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
  st.subheader(f"🪑 Bank ({len(st.session_state.bank_spieler)})")
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
        if st.button(
            "⬅️",
            key=f"to_s11_{name}",
            help="In die Start-11 verschieben",
        ):
          aktuelle_tw = [
              n
              for n in st.session_state.s11_spieler
              if alle_spieler[n]["pos"] == "TW"
          ]
          if pos == "TW" and len(aktuelle_tw) >= 1:
            st.error(f"Bereits ein Torwart vorhanden ({aktuelle_tw[0]})!")
          elif len(st.session_state.s11_spieler) >= 11:
            st.error("Start-11 ist bereits voll (11 Spieler)!")
          else:
            st.session_state.bank_spieler.remove(name)
            st.session_state.s11_spieler.append(name)
            st.rerun()
      with c_del:
        if st.button(
            "✕", key=f"del_bank_{name}", help="Spieler ganz entfernen"
        ):
          st.session_state.bank_spieler.remove(name)
          st.rerun()

st.divider()

# --- 3. BERECHNUNG & BANK-HALTE-LOGIK ---
st.subheader("💰 Kontostand & Minus-Ausgleich")
kontostand = st.number_input(
    "Aktueller Kontostand (€):",
    value=-46799584,
    step=500000,
    format="%d",
)

bank_dict = {
    name: alle_spieler[name]["mw"] for name in st.session_state.bank_spieler
}
s11_dict = {
    name: alle_spieler[name]["mw"] for name in st.session_state.s11_spieler
}
summe_bank_gesamt = sum(bank_dict.values())

m1, m2 = st.columns(2)
m1.metric("Aktueller Kontostand", f"{kontostand:,} €")
m2.metric(
    "Gesamtwert aller Bank-Spieler",
    f"{summe_bank_gesamt:,} €",
    help="Kapitalreserve auf der Bank",
)

# FALL A: Bereits im Plus
if kontostand >= 0:
  st.success(
      f"🎉 Dein Konto ist mit **+{kontostand:,} €** im Plus! Du musst niemanden"
      f" verkaufen und kannst **alle {len(st.session_state.bank_spieler)}"
      " Spieler auf der Bank behalten**."
  )

# FALL B: Minus kann komplett über Bank gedeckt werden
elif kontostand + summe_bank_gesamt >= 0:
  fehlbetrag = abs(kontostand)
  st.info(
      f"Du bist mit **{fehlbetrag:,} €** im Minus. Dein Bankwert reicht aus,"
      " ohne die Start-11 anzugreifen!"
  )
  st.markdown("#### Verkaufsoptionen von der Bank:")

  optionen_bank = []
  for r in range(1, len(bank_dict) + 1):
    for kombi in itertools.combinations(bank_dict.items(), r):
      summe_verkauf = sum(mw for _, mw in kombi)
      if summe_verkauf >= fehlbetrag:
        ueber = summe_verkauf - fehlbetrag
        verkaufte = {n for n, _ in kombi}
        behalten = [
            n for n in st.session_state.bank_spieler if n not in verkaufte
        ]
        optionen_bank.append((kombi, summe_verkauf, ueber, behalten))

  optionen_bank.sort(key=lambda x: (len(x[0]), x[2]))

  for idx, (kombi, summe, restplus, behalten) in enumerate(
      optionen_bank[:5], 1
  ):
    v_text = ", ".join(
        [f"{n} ({alle_spieler[n]['pos']}, {mw:,} €)" for n, mw in kombi]
    )
    b_text = (
        ", ".join([f"{n} ({alle_spieler[n]['pos']})" for n in behalten])
        if behalten
        else "*(Keine - alle Bankspieler verkauft)*"
    )

    with st.expander(
        f"Option {idx}: Nur {len(kombi)} Bankspieler verkaufen — Erlös:"
        f" +{summe:,} € | Behalten: {len(behalten)} Spieler"
    ):
      st.write(f"💸 **Verkaufen:** {v_text}")
      st.write(f"🛡️ **Auf der Bank behalten:** {b_text}")
      st.success(f"**Neuer Kontostand:** +{restplus:,} €")

# FALL C: Gesamte Bank reicht nicht -> S11 muss dazugenommen werden
else:
  fehlbetrag_nach_bank = abs(kontostand + summe_bank_gesamt)
  st.warning(
      f"Selbst der Verkauf der gesamten Bank lässt ein Rest-Minus von"
      f" **{fehlbetrag_nach_bank:,} €** übrig. Deine Start-11 muss"
      " einbezogen werden."
  )

  if not s11_dict:
    st.error("Keine Start-11 Spieler vorhanden, um das Rest-Minus zu decken.")
  else:
    st.markdown("#### Optimale Verkaufsoptionen aus der Start-11:")
    gueltige_s11_optionen = []

    for r in range(1, len(s11_dict) + 1):
      for kombi in itertools.combinations(s11_dict.items(), r):
        summe_verkauf = sum(mw for _, mw in kombi)
        if summe_verkauf >= fehlbetrag_nach_bank:
          verkaufte_namen = {name for name, _ in kombi}
          rest_kader = [
              n for n in st.session_state.s11_spieler if n not in verkaufte_namen
          ]

          hat_tw = any(alle_spieler[n]["pos"] == "TW" for n in rest_kader)
          if len(tw_list) > 0 and not hat_tw:
            continue

          fehlende_linien = []
          if not any(alle_spieler[n]["pos"] == "ABW" for n in rest_kader):
            fehlende_linien.append("ABW")
          if not any(alle_spieler[n]["pos"] == "MIT" for n in rest_kader):
            fehlende_linien.append("MIT")
          if not any(alle_spieler[n]["pos"] == "ANG" for n in rest_kader):
            fehlende_linien.append("ANG")

          ueberschuss = summe_verkauf - fehlbetrag_nach_bank
          gueltige_s11_optionen.append(
              (kombi, summe_verkauf, ueberschuss, fehlende_linien)
          )

    gueltige_s11_optionen.sort(key=lambda x: (len(x[3]), len(x[0]), x[2]))

    if gueltige_s11_optionen:
      for idx, (kombi, summe, restplus, leer) in enumerate(
          gueltige_s11_optionen[:6], 1
      ):
        details = ", ".join(
            [f"{n} ({alle_spieler[n]['pos']}, {mw:,} €)" for n, mw in kombi]
        )
        titel = (
            f"Option {idx}: Alle Bankspieler + {len(kombi)} S11-Spieler"
            f" abgeben — Erlös: +{summe + summe_bank_gesamt:,} €"
        )
        if leer:
          titel += f" ⚠️ (Lücke auf: {', '.join(leer)})"

        with st.expander(titel):
          st.write(
              f"💸 **Aus der Start-11 verkaufen:** {details} *(sowie die"
              " gesamte Bank)*"
          )
          st.success(f"**Neuer Kontostand:** +{restplus:,} €")
          if leer:
            st.caption(
                f"💡 Hinweis: Nach dem Verkauf fehlt dir ein Spieler auf"
                f" {', '.join(leer)}."
            )
    else:
      st.error(
          "Selbst Bank + Start-11 reichen nicht aus, um das Minus zu decken!"
      )

# --- 4. RECHTLICHER DISCLAIMER & FOOTER ---
st.divider()
st.caption(
    "Hinweis: Privates Fan- und Hilfsprojekt. Dieses Tool steht in keiner"
    " offiziellen Verbindung zu Kickbase oder der Kickbase GmbH. Alle"
    " Markennamen und Daten dienen lediglich informativen Zwecken."
)