import streamlit as st
import requests
import time
import os
import json
import random
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Shopify Auto-Pilot Pro", page_icon="🚀", layout="wide")

# Estilos Pro
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1rem;}
    .stSelectbox, .stSlider {margin-bottom: 20px;}
    div[data-testid="stMetricValue"] {color: #008060;} 
    .stButton>button {width: 100%; border-radius: 8px; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# Importaciones y Claves
try:
    import google.generativeai as genai
except ImportError:
    st.error("⚠️ Falta instalar librerías. Ejecuta: pip install google-generativeai apscheduler pytz")
    st.stop()

TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN")
TIENDA_URL = os.environ.get("SHOPIFY_SHOP_URL")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY")
WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")

if TIENDA_URL: TIENDA_URL = TIENDA_URL.replace("https://", "").replace("http://", "").strip("/")
if GOOGLE_KEY: genai.configure(api_key=GOOGLE_KEY)

# Archivo para guardar preferencias del usuario
CONFIG_FILE = "user_config.json"

# --- 2. GESTIÓN DE CONFIGURACIÓN (PERSISTENCIA) ---
def cargar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

# --- 3. FUNCIONES BACKEND SHOPIFY ---

def get_headers():
    if not TOKEN: return {}
    return {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}

def get_collections():
    """Obtiene las colecciones (categorías) de la tienda"""
    if not TOKEN: return []
    url_smart = f"https://{TIENDA_URL}/admin/api/2024-01/smart_collections.json"
    url_custom = f"https://{TIENDA_URL}/admin/api/2024-01/custom_collections.json"
    
    collections = []
    try:
        r1 = requests.get(url_smart, headers=get_headers())
        if r1.status_code == 200: collections += r1.json().get("smart_collections", [])
        
        r2 = requests.get(url_custom, headers=get_headers())
        if r2.status_code == 200: collections += r2.json().get("custom_collections", [])
        
        return collections
    except:
        return []

def get_products_from_collection(collection_id=None, limit=50):
    """Obtiene productos de forma segura"""
    if not TOKEN: return []
    
    if collection_id and collection_id != "all":
        url = f"https://{TIENDA_URL}/admin/api/2024-01/collections/{collection_id}/products.json?limit={limit}"
    else:
        url = f"https://{TIENDA_URL}/admin/api/2024-01/products.json?limit={limit}"
        
    try:
        r = requests.get(url, headers=get_headers())
        if r.status_code == 200:
            return r.json().get("products", [])
        return []
    except:
        return []

# --- 4. CEREBRO IA ADAPTATIVO (A PRUEBA DE FALLOS) ---

def generar_copy_adaptativo(producto, plataforma, tono):
    """Genera contenido optimizado según la red social de forma SEGURA"""
    if not producto: return "Error: Producto no válido."
    
    # --- EXTRACCIÓN SEGURA DE DATOS (AQUÍ ESTABA EL ERROR) ---
    titulo = producto.get('title', 'Producto Genérico')
    
    # Intentamos sacar el precio con cuidado. Si no existe, ponemos 'Consultar'
    precio = "Consultar Web"
    if producto.get('variants') and len(producto['variants']) > 0:
        precio = producto['variants'][0].get('price', 'Consultar Web')
        
    descripcion = producto.get('body_html', '') or ""
    descripcion = descripcion[:200] # Recortamos para no saturar

    if not GOOGLE_KEY: 
        return f"¡Mira este producto! {titulo} a solo {precio}."
    
    # Instrucciones específicas por plataforma
    guia_plataforma = ""
    if plataforma == "Instagram":
        guia_plataforma = "Usa hashtags populares, formato visual, emojis atractivos y CTA en bio."
    elif plataforma == "TikTok":
        guia_plataforma = "Guión viral, corto, energético, usa tendencias y hashtags de TikTok."
    elif plataforma == "Facebook":
        guia_plataforma = "Enfoque en comunidad, beneficios claros y enlace directo."
    elif plataforma == "LinkedIn":
        guia_plataforma = "Tono profesional, enfoque B2B o calidad del producto."

    prompt = f"""
    Actúa como un Social Media Manager Experto.
    Crea el texto (caption) para un post de {plataforma}.
    
    PRODUCTO: {titulo}
    PRECIO: {precio}
    DESCRIPCIÓN: {descripcion}...
    
    TONO: {tono}
    GUÍA PLATAFORMA: {guia_plataforma}
    
    El texto debe ser persuasivo, corto y estar listo para publicar.
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        res = model.generate_content(prompt)
        return res.text
    except:
        # Fallback a modelo anterior si el nuevo falla
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(prompt)
            return res.text
        except:
            return f"¡Novedad increíble! {titulo} disponible por solo {precio}. ¡Corre que vuelan!"

# --- 5. AUTOMATIZACIÓN ---

def tarea_publicar_avanzada(config):
    """Tarea que se ejecuta automáticamente"""
    print(f"⏰ Ejecutando Auto-Pilot Avanzado: {datetime.now()}")
    if not WEBHOOK_URL: return

    col_id = config.get("collection_id", "all")
    productos = get_products_from_collection(col_id)
    
    if not productos:
        print("❌ No se encontraron productos en la colección.")
        return

    cantidad = config.get("cantidad", 1)
    seleccion = random.sample(productos, min(cantidad, len(productos)))
    
    plataforma = config.get("plataforma", "Instagram")
    tono = config.get("tono", "Divertido")

    for prod in seleccion:
        copy = generar_copy_adaptativo(prod, plataforma, tono)
        img = prod['images'][0]['src'] if prod.get('images') else ""
        link = f"https://{TIENDA_URL}/products/{prod['handle']}"
        precio = "N/A"
        if prod.get('variants'):
            precio = prod['variants'][0].get('price', 'N/A')
        
        payload = {
            "plataforma": plataforma,
            "titulo": prod['title'],
            "texto": copy,
            "imagen": img,
            "precio": precio,
            "url": link
        }
        try:
            requests.post(WEBHOOK_URL, json=payload)
            print(f"✅ Enviado ({plataforma}): {prod['title']}")
            time.sleep(3)
        except Exception as e:
            print(f"❌ Error: {e}")

# Iniciar Scheduler
if 'scheduler' not in st.session_state:
    st.session_state.scheduler = BackgroundScheduler()
    st.session_state.scheduler.start()

# --- 6. INTERFAZ GRÁFICA ---

st.title("🤖 Shopify Auto-Pilot Pro")
st.markdown("Configura tu estrategia automática y deja que la IA trabaje mientras duermes.")

if not WEBHOOK_URL:
    st.error("⚠️ Configura el Webhook de Make en los Secrets (MAKE_WEBHOOK_URL).")
    st.stop()

# Cargar configuración guardada
user_conf = cargar_config()

col_izq, col_der = st.columns([1, 2])

with col_izq:
    st.header("⚙️ Preferencias del Robot")
    
    with st.form("config_form"):
        # 1. Configuración de Contenido
        st.subheader("1. Estrategia")
        plataforma = st.selectbox("Red Social Principal", ["Instagram", "Facebook", "TikTok", "LinkedIn"], index=["Instagram", "Facebook", "TikTok", "LinkedIn"].index(user_conf.get("plataforma", "Instagram")))
        tono = st.select_slider("Tono de Voz", options=["Divertido", "Urgente", "Informativo", "Profesional", "Lujoso"], value=user_conf.get("tono", "Divertido"))
        
        # 2. Fuente de Productos
        st.subheader("2. ¿Qué promocionar?")
        cols = get_collections()
        opciones_col = {"Todo el inventario": "all"}
        for c in cols:
            opciones_col[c['title']] = c['id']
            
        # Recuperar selección
        idx_col = 0
        saved_col = user_conf.get("collection_id", "all")
        keys = list(opciones_col.keys())
        values = list(opciones_col.values())
        if saved_col in values:
            idx_col = values.index(saved_col)
            
        col_seleccionada = st.selectbox("Selecciona Colección", keys, index=idx_col)
        
        # 3. Frecuencia y Hora
        st.subheader("3. Calendario")
        zona_horaria = st.selectbox("Tu Zona Horaria", pytz.all_timezones, index=pytz.all_timezones.index(user_conf.get("timezone", "Europe/Madrid")))
        cantidad = st.number_input("Posts por día", min_value=1, max_value=10, value=user_conf.get("cantidad", 2))
        
        saved_time = user_conf.get("hora", "10:00")
        try:
            hora_obj = datetime.strptime(saved_time, "%H:%M").time()
        except:
            hora_obj = datetime.strptime("10:00", "%H:%M").time()
        
        hora = st.time_input("Hora de publicación", value=hora_obj)
        
        guardar = st.form_submit_button("💾 Guardar y Activar Automatización", type="primary")
        
        if guardar:
            nuevo_conf = {
                "plataforma": plataforma,
                "tono": tono,
                "collection_id": opciones_col[col_seleccionada],
                "timezone": zona_horaria,
                "cantidad": cantidad,
                "hora": hora.strftime("%H:%M")
            }
            guardar_config(nuevo_conf)
            
            st.session_state.scheduler.remove_all_jobs()
            st.session_state.scheduler.add_job(
                tarea_publicar_avanzada,
                'cron',
                hour=hora.hour,
                minute=hora.minute,
                args=[nuevo_conf],
                timezone=pytz.timezone(zona_horaria)
            )
            st.toast("¡Configuración guardada!", icon="✅")
            time.sleep(1)
            st.rerun()

with col_der:
    st.header("📊 Estado y Vista Previa")
    
    jobs = st.session_state.scheduler.get_jobs()
    if jobs:
        next_run = jobs[0].next_run_time
        st.success(f"✅ **ROBOT ACTIVO**")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Próxima publicación", next_run.strftime("%H:%M"))
        m2.metric("Red Social", user_conf.get("plataforma", "-"))
        m3.metric("Colección", col_seleccionada if 'col_seleccionada' in locals() else "Todas")
    else:
        st.warning("⚠️ El robot está detenido. Guarda la configuración.")

    st.markdown("---")
    st.subheader("🧪 Prueba de Laboratorio")
    st.write("Genera un ejemplo de cómo se vería un post:")
    
    if st.button("Generar Post de Ejemplo"):
        with st.spinner("La IA está creando el contenido..."):
            # Obtenemos el ID de la colección seleccionada actualmente en el selectbox
            current_col_id = opciones_col.get(col_seleccionada, "all")
            
            prod_ejemplo = get_products_from_collection(current_col_id, limit=3)
            
            if prod_ejemplo and len(prod_ejemplo) > 0:
                p = prod_ejemplo[0]
                if p:
                    copy_demo = generar_copy_adaptativo(p, plataforma, tono)
                    
                    st.markdown(f"### 📱 Vista Previa: {plataforma}")
                    img_url = p['images'][0]['src'] if p.get('images') else "https://via.placeholder.com/300"
                    st.image(img_url, width=300)
                    st.caption(f"**Copy generado ({tono}):**")
                    st.text_area("", value=copy_demo, height=200)
                else:
                    st.error("Error al leer el producto.")
            else:
                st.warning("No se encontraron productos en esa colección para probar. Prueba con 'Todo el inventario'.")

    st.markdown("---")
    if st.button("🚀 Forzar Publicación Real AHORA"):
        conf_actual = cargar_config()
        if conf_actual:
            with st.spinner("Enviando a Make..."):
                tarea_publicar_avanzada(conf_actual)
            st.success("¡Enviado a Make! Revisa tus redes.")
        else:
            st.error("Guarda la configuración primero.")
