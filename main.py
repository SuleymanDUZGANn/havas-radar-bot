import os
import time
import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

TELEGRAM_BOT_TOKEN = "8651100759:AAGrnwFEgP3KvBYXEipDgTGxICoGbU9zkb8"
TELEGRAM_CHAT_ID = "1219290602"

WATCHLIST = {
    "WSA9583": {"pp": "—"}, "N1F": {"pp": "—"}, "KZN9410": {"pp": "—"}, "LO137": {"pp": "—"},
    "TO3422": {"pp": "—"}, "BA720": {"pp": "—"}, "KL1961": {"pp": "—"}, "TU216": {"pp": "—"},
    "MS745": {"pp": "F5L"}, "AF1390": {"pp": "B3R"}, "JU426": {"pp": "B5R"}, "ET720": {"pp": "—"},
    "TG900": {"pp": "D20"}, "TBN7281": {"pp": "F15"}, "PC3306": {"pp": "G6L"}, "UPS268": {"pp": "K54"},
    "GQ670": {"pp": "A2R"}, "DV485": {"pp": "—"}, "W62429": {"pp": "A3R"}, "SHR5291": {"pp": "B13"},
    "RO261": {"pp": "B5R"}, "TBZ6617": {"pp": "B9L"}, "ME265": {"pp": "—"}, "LO2101": {"pp": "—"},
    "U6773": {"pp": "—"}, "PC1981": {"pp": "—"}, "B99735": {"pp": "—"}, "TU214": {"pp": "—"},
    "B99731": {"pp": "—"}, "QB2213": {"pp": "—"}, "B99746": {"pp": "—"}, "QR239": {"pp": "B4"},
    "BA716": {"pp": "A3R"}, "SU2172": {"pp": "—"}, "RJ165": {"pp": "—"}, "4O404": {"pp": "A10R"},
    "MS737": {"pp": "—"}, "LO133": {"pp": "—"}, "W95327": {"pp": "—"}, "TCKYA": {"pp": "—"},
    "ME263": {"pp": "—"}, "UX1683": {"pp": "—"}, "SU656": {"pp": "—"}, "SM303": {"pp": "F5R"},
    "4O400": {"pp": "—"}, "SU2136": {"pp": "—"}, "B99709": {"pp": "B9L"}, "BT711": {"pp": "—"},
    "S73749": {"pp": "—"}, "4O402": {"pp": "—"}, "SU640": {"pp": "—"}, "SU2130": {"pp": "—"},
    "JU422": {"pp": "—"}, "TO3288": {"pp": "—"}, "KL1959": {"pp": "—"}, "LO135": {"pp": "—"},
    "WY165": {"pp": "—"}, "MS735": {"pp": "—"}, "RO263": {"pp": "—"}, "TBN7273": {"pp": "—"},
    "QR245": {"pp": "—"}, "RB443": {"pp": "—"}, "BA718": {"pp": "—"}, "PC1983": {"pp": "—"},
    "W95729": {"pp": "—"}, "ME267": {"pp": "—"}, "UD761": {"pp": "—"}, "PC3300": {"pp": "—"},
    "RJ163": {"pp": "—"}, "VY3078": {"pp": "—"}, "ET722": {"pp": "—"}, "B99700": {"pp": "—"},
    "SM3618": {"pp": "—"}, "TBZ6619": {"pp": "—"}, "SU812": {"pp": "—"}, "QR237": {"pp": "B4"},
    "SQ392": {"pp": "D9"}, "KM784": {"pp": "B6R"}, "SZ103": {"pp": "A8L"}, "DWC050": {"pp": "—"},
    "TO3420": {"pp": "—"}, "UD161": {"pp": "B9R"}, "SU630": {"pp": "B18R"}, "B99710": {"pp": "—"},
    "B99718": {"pp": "—"}, "TS214": {"pp": "—"}, "JNJ652": {"pp": "—"}, "QR8218": {"pp": "—"},
    "RH9493": {"pp": "—"}, "FV6963": {"pp": "—"}, "WZ4655": {"pp": "—"}, "RJ860": {"pp": "—"},
    "ZT670": {"pp": "—"}, "ET3769": {"pp": "—"}, "SHR5293": {"pp": "—"}, "LO2301": {"pp": "—"},
    "FG719": {"pp": "—"}, "VY3180": {"pp": "—"}, "RO265": {"pp": "—"}, "MS542": {"pp": "—"},
    "SU2132": {"pp": "—"}, "JU2428": {"pp": "—"}, "TCNKS": {"pp": "—"}, "SU892": {"pp": "—"},
    "JU1424": {"pp": "—"}, "TCASL": {"pp": "—"}, "RH9489": {"pp": "—"}, "W62435": {"pp": "—"}
}

ICAO_PREFIX_MAP = {
    "IRZ": "B9", "AFL": "SU", "THY": "TK", "PGT": "PC",
    "ROT": "RO", "LOT": "LO", "ETH": "ET", "QTR": "QR",
    "BAW": "BA", "KLM": "KL", "AFR": "AF", "ASL": "JU"
}

notified_60m = set()
notified_30m = set()
notified_landed = set()

def clean_code(val):
    return re.sub(r"[^A-Z0-9]", "", str(val).upper()) if val else ""

CLEAN_WATCHLIST = {clean_code(k): (k, v) for k, v in WATCHLIST.items()}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK - Havas Radar Calisiyor")

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram gonderim hatasi: {e}")
        return False

def get_fr24_ist_flights():
    url = "https://api.flightradar24.com/common/v1/airport.json?code=ist&plugin[]=&plugin-setting[schedule][mode]=arrivals&page=1&limit=100"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            return r.json().get("result", {}).get("response", {}).get("airport", {}).get("pluginData", {}).get("schedule", {}).get("arrivals", {}).get("data", [])
        else:
            print(f"FR24 API Yanit Kodu: {r.status_code}")
    except Exception as err:
        print(f"Radar veri cekme hatasi: {err}")
    return []

def match_flight(flight_number, callsign):
    c_number = clean_code(flight_number)
    c_callsign = clean_code(callsign)

    if c_number in CLEAN_WATCHLIST:
        return CLEAN_WATCHLIST[c_number]
    if c_callsign in CLEAN_WATCHLIST:
        return CLEAN_WATCHLIST[c_callsign]

    for icao_pre, iata_pre in ICAO_PREFIX_MAP.items():
        if c_callsign.startswith(icao_pre):
            conv = iata_pre + c_callsign[len(icao_pre):]
            if conv in CLEAN_WATCHLIST:
                return CLEAN_WATCHLIST[conv]

    for clean_k, val in CLEAN_WATCHLIST.items():
        if (clean_k and clean_k in c_number) or (c_number and c_number in clean_k):
            return val
        if (clean_k and clean_k in c_callsign) or (c_callsign and c_callsign in clean_k):
            return val

    return None, None

def run_radar():
    print("Radar dongusu aktif...")
    send_telegram("🚀 <b>Havaş IST Radar Sistemi Canlı Yayında!</b>\n\n• Frekans Yaklaşma (30-60 dk)\n• Son Yaklaşma (<30 dk)\n• Teker Koyma (İniş)")

    while True:
        try:
            flights = get_fr24_ist_flights()
            now_ts = int(time.time())

            approaching_30m = []
            approaching_60m = []

            for f in flights:
                f_info = f.get("flight", {})
                f_ident = f_info.get("identification", {})
                f_number = f_ident.get("number", {}).get("default") or ""
                f_callsign = f_ident.get("callsign") or ""

                original_key, watch_data = match_flight(f_number, f_callsign)
                if not original_key:
                    continue

                aircraft = f_info.get("aircraft", {}).get("model", {}).get("text", "—")
                reg = f_info.get("aircraft", {}).get("registration", "—")
                origin = f_info.get("airport", {}).get("origin", {}).get("code", {}).get("iata", "—")
                pp = watch_data["pp"]

                status_obj = f_info.get("status", {})
                generic_status = str(status_obj.get("generic", {}).get("status", {}).get("text", "")).lower()

                time_info = f_info.get("time", {})
                real_landing = time_info.get("real", {}).get("arrival")
                est_landing = time_info.get("estimated", {}).get("arrival") or time_info.get("scheduled", {}).get("arrival")

                # 1. TEKER KOYMA (İNİŞ)
                if "landed" in generic_status or real_landing is not None:
                    if original_key not in notified_landed:
                        notified_landed.add(original_key)
                        land_time = time.strftime('%H:%M', time.localtime(real_landing)) if real_landing else "Az önce"
                        msg = (
                            f"✅ <b>TEKER KOYDU (İNDİ)!</b>\n\n"
                            f"✈️ <b>{original_key}</b> ({origin} ➔ İST)\n"
                            f"📍 <b>PP:</b> <code>{pp}</code>\n"
                            f"🛬 <b>Teker Saati:</b> {land_time}\n"
                            f"🏷️ {reg} | {aircraft}"
                        )
                        send_telegram(msg)
                    continue

                # 2. SÜRE HESABI
                if est_landing and original_key not in notified_landed:
                    diff_min = (est_landing - now_ts) // 60
                    flight_card = {
                        "key": original_key,
                        "origin": origin,
                        "pp": pp,
                        "reg": reg,
                        "aircraft": aircraft,
                        "eta": time.strftime('%H:%M', time.localtime(est_landing)),
                        "diff": diff_min
                    }

                    if 0 < diff_min <= 30:
                        approaching_30m.append(flight_card)
                    elif 30 < diff_min <= 60:
                        approaching_60m.append(flight_card)

            # --- SON YAKLAŞMA (<30 DK) LİSTESİ ---
            approaching_30m.sort(key=lambda x: x["diff"])
            new_30m = [fl for fl in approaching_30m if fl["key"] not in notified_30m]
            if new_30m:
                lines = ["🚨 <b>SON YAKLAŞMA (&lt;30 DK KALANLAR)</b>\n"]
                for fl in approaching_30m:
                    lines.append(
                        f"⏱ <b>{fl['diff']} dk</b> | ETA: {fl['eta']}\n"
                        f"✈️ <b>{fl['key']}</b> ({fl['origin']} ➔ İST) | PP: <code>{fl['pp']}</code>\n"
                        f"🏷️ {fl['reg']} ({fl['aircraft']})\n"
                        f"──────────────"
                    )
                    notified_30m.add(fl["key"])
                send_telegram("\n".join(lines))

            # --- FREKANSA GİRECEK (30-60 DK) LİSTESİ ---
            approaching_60m.sort(key=lambda x: x["diff"])
            new_60m = [fl for fl in approaching_60m if fl["key"] not in notified_60m and fl["key"] not in notified_30m]
            if new_60m:
                lines = ["📡 <b>FREKANSA GİRECEK UÇAKLAR (30-60 DK)</b>\n"]
                for fl in approaching_60m:
                    lines.append(
                        f"⏱ <b>{fl['diff']} dk sonra</b> | ETA: {fl['eta']}\n"
                        f"✈️ <b>{fl['key']}</b> ({fl['origin']} ➔ İST) | PP: <code>{fl['pp']}</code>\n"
                        f"🏷️ {fl['reg']} ({fl['aircraft']})\n"
                        f"──────────────"
                    )
                    notified_60m.add(fl["key"])
                send_telegram("\n".join(lines))

            time.sleep(30)

        except Exception as loop_err:
            print(f"Dongu hatasi: {loop_err}")
            time.sleep(20)

if __name__ == "__main__":
    web_thread = threading.Thread(target=start_dummy_server, daemon=True)
    web_thread.start()
    run_radar()
