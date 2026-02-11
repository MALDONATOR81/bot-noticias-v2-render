from flask import Flask
from threading import Thread
import requests
import feedparser
import time
import os
import signal
import sys
from datetime import datetime

# === LATIDO DEL BOT (Monitor anti-cuelgue) ===
ultimo_latido = time.time()

# === CONFIGURACIÓN ===
TELEGRAM_TOKEN = "832957113:AAHobf4jrHQQ-aMf5DMkY98Khi-vQjhIu6o"
CHAT_ID = "8298601106"

HISTORIAL_FILE = "notificados.txt"
LOG_FILE = "registro.log"
ULTIMO_RESUMEN_FILE = "ultimo_resumen.txt"

# === PALABRAS CLAVE ===
GENERAL_KEYWORDS = [
    "droga","drogas","narcotráfico","tráfico de drogas","narcos","cocaína","hachís","heroína",
    "contrabando","tabaco ilegal","inmigración ilegal","patera","cayuco",
    "vehículo robado","coche robado","documento falso","falsificación",

    "terrorismo","terrorista","yihadismo","atentado","explosivo","célula terrorista",
    "estado islámico","daesh","isis","al qaeda",

    "terrorisme","terroriste","attentat","cellule terroriste","etat islamique",

    "إرهاب","إرهابي","تفجير","خلية إرهابية","داعش","القاعدة"
]

# === FUENTES RSS ===
RSS_FEEDS = [
    "https://fr.le360.ma/rss",
    "https://www.hespress.com/feed",
    "https://www.yabiladi.com/rss/news.xml",
    "https://www.hibapress.com/feed",
    "https://elfarodeceuta.es/feed",
    "https://www.ceutaactualidad.com/rss/",
    "https://www.ceutaldia.com/rss/",
    "https://www.melillaactualidad.com/rss/"
]

# === FUNCIONES UTILITARIAS ===

def cargar_ids_notificados():
    if not os.path.exists(HISTORIAL_FILE):
        return set()
    with open(HISTORIAL_FILE, 'r', encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def guardar_id_notificado(uid):
    with open(HISTORIAL_FILE, "a", encoding="utf-8") as f:
        f.write(uid + "\n")
    notificados.add(uid)

def log_event(txt):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {txt}\n")

def contiene_palabra_clave(texto):
    texto_low = (texto or "").lower()
    for palabra in GENERAL_KEYWORDS:
        if palabra.lower() in texto_low:
            return True
    return False

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(
            url,
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=20
        )
        if r.status_code != 200:
            log_event(f"❌ Telegram {r.status_code}: {r.text}")
    except Exception as e:
        log_event(f"❌ Error Telegram: {e}")

# === RESUMEN DIARIO (como el bot anterior) ===

def resumen_diario_ya_enviado():
    if not os.path.exists(ULTIMO_RESUMEN_FILE):
        return False
    with open(ULTIMO_RESUMEN_FILE, "r", encoding="utf-8") as f:
        return f.read().strip() == datetime.now().strftime("%Y-%m-%d")

def marcar_resumen_enviado():
    with open(ULTIMO_RESUMEN_FILE, "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime("%Y-%m-%d"))

def enviar_resumen_diario():
    if resumen_diario_ya_enviado():
        return

    hoy = datetime.now().strftime("%Y-%m-%d")
    resumenes = []

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            for linea in f:
                if hoy in linea and "✅ Enviada noticia:" in linea:
                    partes = linea.strip().split("✅ Enviada noticia: ")
                    if len(partes) > 1:
                        resumenes.append(partes[1])

    texto = f"🗞️ <b>Resumen diario ({hoy})</b>\n\n"
    if resumenes:
        texto += f"✅ {len(resumenes)} noticias enviadas hoy:\n"
        texto += "\n".join([f"• {t}" for t in resumenes])
    else:
        texto += "No se enviaron noticias hoy."

    enviar_telegram(texto)
    marcar_resumen_enviado()

# === FUNCIONES PRINCIPALES ===

def revisar_rss():
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                uid = link or title

                if uid in notificados:
                    continue

                texto = f"{title} {summary}"
                if contiene_palabra_clave(texto):
                    mensaje = f"📰 <b>{title}</b>\n🔗 {link}"
                    enviar_telegram(mensaje)
                    guardar_id_notificado(uid)
                    log_event(f"✅ Enviada noticia: {title}")

        except Exception as e:
            log_event(f"⚠️ Error en feed {url}: {e}")

# === MONITOR ANTI-CUELGUE ===

def monitor_actividad():
    while True:
        if time.time() - ultimo_latido > 180:
            enviar_telegram("⚠️ El bot dejó de latir. Posible cuelgue o apagado inesperado.")
            log_event("❗ Latido perdido. Forzando salida.")
            os._exit(1)
        time.sleep(60)

Thread(target=monitor_actividad, daemon=True).start()

# === FLASK KEEP ALIVE ===
app = Flask('')

@app.route('/')
def home():
    return "Bot activo 🚀"

@app.route('/test')
def test():
    enviar_telegram("✅ Test OK desde Render")
    return "Test enviado"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)

def keep_alive():
    Thread(target=run).start()

# === MANEJO DE SEÑALES (parada limpia) ===

def manejar_salida_graciosa(signum, frame):
    enviar_telegram("⚠️ El bot de noticias se ha detenido (señal recibida)")
    log_event("⚠️ Bot detenido por señal")
    sys.exit(0)

signal.signal(signal.SIGINT, manejar_salida_graciosa)
signal.signal(signal.SIGTERM, manejar_salida_graciosa)

# === INICIO ===
notificados = cargar_ids_notificados()
keep_alive()

enviar_telegram("✅ Bot iniciado")
log_event("🟢 Bot iniciado")

try:
    while True:
        ultimo_latido = time.time()
        revisar_rss()

        # Resumen diario a las 23:55
        if datetime.now().strftime("%H:%M") == "23:55":
            enviar_resumen_diario()

        time.sleep(60)

except Exception as e:
    msg = f"❌ Error:\n{e}"
    enviar_telegram(msg)
    log_event(msg)

finally:
    enviar_telegram("⚠️ Bot desconectado")
    log_event("⚠️ Bot desconectado (bloque finally)")
