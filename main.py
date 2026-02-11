from flask import Flask
from threading import Thread
import requests
import feedparser
import time
import re
import os
import signal
import sys
from datetime import datetime

# === LATIDO DEL BOT (Monitor anti-cuelgue) ===
ultimo_latido = time.time()

def monitor_actividad():
    while True:
        if time.time() - ultimo_latido > 180:
            enviar_telegram("⚠️ El bot dejó de latir. Posible cuelgue o apagado inesperado.")
            log_event("❗ Latido perdido. Forzando salida.")
            os._exit(1)
        time.sleep(60)

Thread(target=monitor_actividad, daemon=True).start()

# === CONFIGURACIÓN ===
TELEGRAM_TOKEN = "PON_AQUI_TU_NUEVO_TOKEN"
CHAT_ID = "8298601106"

HISTORIAL_FILE = "notificados.txt"
LOG_FILE = "registro.log"
ULTIMO_RESUMEN_FILE = "ultimo_resumen.txt"

# === PALABRAS CLAVE ===
GENERAL_KEYWORDS = [
    # ---- TU LISTA ORIGINAL COMPLETA ----
    "droga", "drogas", "narcotráfico", "tráfico de drogas", "narcos", "cocaína", "cocaina",
    "hachís", "hachis", "heroína", "heroina", "lsd", "éxtasis", "extasis", "mdma", "ketamina",
    "alucinógenos", "psicotrópicos", "estupefacientes", "sustancias ilícitas", "sustancias prohibidas",
    "contrabando", "mercancía ilegal", "tabaco ilegal", "cajetillas", "cigarrillos",
    "inmigración ilegal", "inmigración irregular", "migrantes ilegales", "patera", "cayuco", "frontera sur",
    "saltos de valla", "vehículo robado", "vehículos robados", "coche robado", "coches robados",
    "moto robada", "motos robadas", "matrícula falsa", "matrículas falsas", "matrículas duplicadas",
    "documento falso", "documentación falsa", "papeles falsos", "falsificación", "fraude documental",

    "trafic de drogue", "drogue", "drogues", "cocaïne", "hachisch", "héroïne", "psychotropes",
    "hallucinogènes", "stupéfiants", "substances illicites", "ecstasy", "lsd", "mdma", "kétamine",
    "contrebande", "tabac de contrebande", "cigarettes", "marchandises illégales", "immigration illégale",
    "immigration clandestine", "migrants illégaux", "passeur", "passeurs", "bateau de migrants", "barque",
    "franchissement illégal", "véhicule volé", "véhicules volés", "voiture volée", "voitures volées",
    "moto volée", "motos volées", "plaque falsifiée", "plaques falsifiées", "plaque dupliquée",
    "plaques dupliquées", "faux documents", "falsification de documents", "fraude documentaire",

    "مخدرات", "مخدر", "كوكايين", "حشيش", "هيروين", "حبوب مهلوسة", "مؤثرات عقلية", "حبوب",
    "مواد مخدرة", "أقراص مخدرة", "أقراص مهلوسة", "التهريب", "السجائر المهربة", "سجائر مهربة",
    "تبغ مهرب", "بضائع مهربة", "ممنوعات", "الهجرة السرية", "الهجرة غير الشرعية", "الهجرة غير النظامية",
    "مهاجرين سريين", "قارب", "قوارب الموت", "مهاجرين غير شرعيين", "سيارة مسروقة", "سيارات مسروقة",
    "مركبة مسروقة", "مركبات مسروقة", "دراجة نارية مسروقة", "دراجات نارية مسروقة", "لوحة مزورة",
    "لوحات مزورة", "وثائق مزورة", "تزوير الوثائق", "تزوير",

    # ---- TERRORISMO ES ----
    "terrorismo","terrorista","terroristas","yihadismo","yihadista","yihadistas",
    "atentado","atentados","explosión","explosion","explosivo","explosivos",
    "célula","celula","célula terrorista","celula terrorista",
    "radicalización","radicalizacion","reclutamiento",
    "estado islámico","estado islamico","daesh","isis","al qaeda","aqmi",

    # ---- TERRORISMO FR ----
    "terrorisme","terroriste","terroristes",
    "djihadisme","djihadiste","djihadistes",
    "attentat","attentats","explosif","explosifs",
    "cellule terroriste","radicalisation","recrutement",
    "etat islamique","état islamique","daech","al qaida",

    # ---- TERRORISMO AR ----
    "إرهاب","ارهاب","إرهابي","إرهابية","تطرف",
    "جهاد","جهادي","تفجير","متفجرات",
    "خلية إرهابية","داعش","تنظيم الدولة","القاعدة"
]

COMBINACIONES_ESPECIALES = [
    ("véhicule","volé"),("véhicules","volés"),
    ("voiture","volée"),("voitures","volées"),
    ("moto","volée"),("motos","volées"),
    ("plaque","dupliquée"),("plaques","dupliquées"),
    ("document","faux"),("falsification","documents"),
    ("خلية","إرهابية"),
    ("célula","terrorista"),
    ("cellule","terroriste")
]

COMBINACIONES_TRIPLES = [
    ("ministerio","interior","informe estadístico"),
    ("ministerio","interior","balance"),
    ("ministerio","interior","memorándum"),
    ("ministère","intérieur","rapport statistique"),
    ("ministère","intérieur","bilan"),
    ("ministère","intérieur","mémorandum"),
    ("وزارة","الداخلية","تقرير إحصائي"),
    ("وزارة","الداخلية","حصيلة"),
    ("وزارة","الداخلية","مذكرة")
]

# === FUENTES RSS ===
RSS_FEEDS = [
    "https://fr.le360.ma/rss",
    "https://www.hespress.com/feed",
    "https://www.yabiladi.com/rss/news.xml",
    "https://www.hibapress.com/feed",

    # CEUTA
    "https://elfarodeceuta.es/feed",
    "https://elfarodeceuta.es/sucesos-seguridad/feed",
    "https://www.ceutaactualidad.com/rss/",
    "https://www.ceutaldia.com/rss/",

    # MELILLA
    "https://www.melillaactualidad.com/rss/"
]

# === FUNCIONES ===

def cargar_ids_notificados():
    if not os.path.exists(HISTORIAL_FILE):
        return set()
    with open(HISTORIAL_FILE, 'r') as f:
        return set(line.strip() for line in f)

def guardar_id_notificado(uid):
    with open(HISTORIAL_FILE, "a") as f:
        f.write(uid+"\n")
    notificados.add(uid)

def log_event(txt):
    with open(LOG_FILE,"a",encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {txt}\n")

def contiene_palabra_clave(texto):
    texto_low = texto.lower()

    for palabra in GENERAL_KEYWORDS:
        if palabra.lower() in texto_low:
            return True

    for a,b in COMBINACIONES_ESPECIALES:
        if a.lower() in texto_low and b.lower() in texto_low:
            return True

    for a,b,c in COMBINACIONES_TRIPLES:
        if a.lower() in texto_low and b.lower() in texto_low and c.lower() in texto_low:
            return True

    return False

def enviar_telegram(msg):
    try:
        url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url,data={"chat_id":CHAT_ID,"text":msg,"parse_mode":"HTML"})
    except Exception as e:
        log_event(f"Error Telegram: {e}")

def revisar_rss():
    for url in RSS_FEEDS:
        try:
            feed=feedparser.parse(url)
            for entry in feed.entries:
                link=entry.get("link","")
                title=entry.get("title","")
                summary=entry.get("summary","")
                uid=link or title

                if uid in notificados:
                    continue

                texto=f"{title} {summary}"
                if contiene_palabra_clave(texto):
                    mensaje=f"📰 <b>{title}</b>\n🔗 {link}"
                    enviar_telegram(mensaje)
                    guardar_id_notificado(uid)
                    log_event(f"Enviada: {title}")

        except Exception as e:
            log_event(f"Error en feed {url}: {e}")

# === FLASK KEEP ALIVE ===
app=Flask('')

@app.route('/')
def home():
    return "Bot activo 🚀"

def run():
    app.run(host='0.0.0.0',port=8080)

Thread(target=run).start()

# === INICIO ===
notificados=cargar_ids_notificados()
enviar_telegram("✅ Bot iniciado")

while True:
    ultimo_latido=time.time()
    revisar_rss()
    time.sleep(60)
