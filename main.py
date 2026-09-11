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

# ICAO -> IATA havayolu kod dönüşümleri (gerekirse otomatik yakalasın diye)
ICAO_PREFIX_MAP = {
    "IRZ": "B9",  # Iran Airtour
    "AFL": "SU",  # Aeroflot
    "THY": "TK",
    "PGT": "PC",
    "ROT": "RO",
    "LOT": "LO",
    "ETH": "ET",
    "QTR": "QR",
    "BAW": "BA",
    "KLM": "KL",
    "AFR": "AF",
    "ASL": "JU"
}

notified_30m = set()
notified_landed = set()

def clean_code(val):
    if not val:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(val).upper())

# Watchlist anahtarlarını normalize et
CLEAN_WATCHLIST = {clean_code(k): (k, v) for k, v in WATCHLIST.items()}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK - Havas Radar Aktif")

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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Mesaj iletilemedi: {e}")

def get_fr24_ist_flights():
    url = "https://api.flightradar24.com/common/v1/airport.json?code=ist&plugin[]=&plugin-setting[schedule][mode]=arrivals&page=1&limit=100"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            return r.json().get("result", {}).get("response", {}).get("airport", {}).get("pluginData", {}).get("schedule", {}).get("arrivals", {}).get("data", [])
    except Exception as err:
        print(f"Radar veri hatasi: {err}")
    return []

def match_flight(flight_number, callsign):
    c_number = clean_code(flight_number)
    c_callsign = clean_code(callsign)

    # 1. Doğrudan numara eşleşmesi
    if c_number in CLEAN_WATCHLIST:
        return CLEAN_WATCHLIST[c_number]

    # 2. Doğrudan çağrı kodu eşleşmesi
    if c_callsign in CLEAN_WATCHLIST:
        return CLEAN_WATCHLIST[c_callsign]

    # 3. ICAO kodunu IATA'ya çevirip kontrol etme (örn: IRZ9710 -> B99710)
    for icao_pre, iata_pre in ICAO_PREFIX_MAP.items():
        if c_callsign.startswith(icao_pre):
            converted = iata_pre + c_callsign[len(icao_pre):]
            if converted in CLEAN_WATCHLIST:
                return CLEAN_WATCHLIST[converted]

    # 4. Parçalı içerik eşleşmesi
    for clean_k, val in CLEAN_WATCHLIST.items():
        if (clean_k and clean_k in c_number) or (c_number and c_number in clean_k):
            return val
        if (clean_k and clean_k in c_callsign) or (c_callsign and c_callsign in clean_k):
            return val

    return None, None

def run_radar():
    print("Havaş Radarı Başlatıldı.")
    send_telegram("🚀 <b>Havaş IST Operasyon Radarı Devrede</b>\n\nTakip Listesi: 92 Uçuş\n* İnişe <30 dk kalanlar dakikaya göre sıralı liste\n* Teker koyanlar anlık onaylı bildirim")

    while True:
        try:
            flights = get_fr24_ist_flights()
            now_ts = int(time.time())
            approaching_flights = []

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

                # TEKER KOYDU (İNİŞ) BİLDİRİMİ
                if "landed" in generic_status or real_landing is not None:
                    if original_key not in notified_landed:
                        notified_landed.add(original_key)
                        land_time = time.strftime('%H:%M', time.localtime(real_landing)) if real_landing else "Az önce"
                        msg = (
                            f"✅ <b>TEKER KOYDU (İNDİ)!</b>\n\n"
                            f"✈️ <b>{original_key}</b> ({origin} ➔ İST)\n"
                            f"📍 Park Pozisyonu (PP): <code>{pp}</code>\n"
                            f"🛬 Teker Saati: <b>{land_time}</b>\n"
                            f"🏷️ Kuyruk / Tip: {reg} | {aircraft}"
                        )
                        send_telegram(msg)
                        print(f"[İNDİ]: {original_key}")
                    continue

                # 30 DAKİKADAN AZ KALANLAR
                if est_landing and original_key not in notified_landed:
                    diff_min = (est_landing - now_ts) // 60
                    if 0 < diff_min <= 30:
                        approaching_flights.append({
                            "key": original_key,
                            "origin": origin,
                            "pp": pp,
                            "reg": reg,
                            "aircraft": aircraft,
                            "eta": time.strftime('%H:%M', time.localtime(est_landing)),
                            "diff": diff_min
                        })

            # Dakikaya göre en yakından uzağa sıralama
            approaching_flights.sort(key=lambda x: x["diff"])

            # Henüz bildirilmemiş yeni bir uçak hatta girdiyse güncel listeyi bas
            new_faces = [fl for fl in approaching_flights if fl["key"] not in notified_30m]
            if new_faces:
                summary_lines = ["🚨 <b>YAKLAŞMA HATTI (&lt;30 DK KALANLAR)</b>\n"]
                for fl in approaching_flights:
                    summary_lines.append(
                        f"⏱ <b>{fl['diff']} dk kaldı</b> | ETA: {fl['eta']}\n"
                        f"✈️ <b>{fl['key']}</b> ({fl['origin']} ➔ İST) | PP: <code>{fl['pp']}</code>\n"
                        f"🏷️ {fl['reg']} ({fl['aircraft']})\n"
                        f"──────────────"
                    )
                    notified_30m.add(fl["key"])

                send_telegram("\n".join(summary_lines))
                print(f"[YAKLAŞMA]: {len(approaching_flights)} uçak listelendi.")

            time.sleep(35)

        except Exception as loop_err:
            print(f"Hata: {loop_err}")
            time.sleep(25)

if __name__ == "__main__":
    web_thread = threading.Thread(target=start_dummy_server, daemon=True)
    web_thread.start()
    run_radar()
