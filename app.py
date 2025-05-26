import streamlit as st
import pandas as pd
from PIL import Image
import pytesseract
import PyPDF2
import io
import re
from io import BytesIO
import numpy as np

# Importaciones opcionales para voz (solo funcionan localmente)
try:
    import speech_recognition as sr
    import pyttsx3
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

# Configuración
st.set_page_config(page_title="Cambio de Precios", layout="wide")

# Variables de estado
if 'df' not in st.session_state:
    st.session_state.df = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Funciones de procesamiento
def extract_text_from_pdf(pdf_file):
    text = ""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_image(image):
    return pytesseract.image_to_string(image)

def extract_prices_from_text(text):
    # Regex para encontrar precios
    price_pattern = r'\$?(\d+(?:\.\d{2})?|\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
    prices = re.findall(price_pattern, text)
    return [float(p.replace(',', '')) for p in prices]

def process_uploaded_file(uploaded_file):
    if uploaded_file.type == "application/pdf":
        text = extract_text_from_pdf(uploaded_file)
        prices = extract_prices_from_text(text)
        return pd.DataFrame({'precio': prices})
    
    elif uploaded_file.type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                               "application/vnd.ms-excel"]:
        df = pd.read_excel(uploaded_file)
        return df
    
    elif uploaded_file.type.startswith('image/'):
        image = Image.open(uploaded_file)
        text = extract_text_from_image(image)
        prices = extract_prices_from_text(text)
        return pd.DataFrame({'precio': prices})
    
    return None

def speech_to_text():
    if not VOICE_AVAILABLE:
        return "Voz no disponible en este entorno"
    
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.write("Hablando...")
        audio = r.listen(source, timeout=5)
    try:
        text = r.recognize_google(audio, language='es-ES')
        return text
    except:
        return "Error reconociendo voz"

def text_to_speech(text):
    if not VOICE_AVAILABLE:
        return
    
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

def process_price_command(command, df):
    # IA para interpretar comandos
    prompt = f"""
    Tienes un DataFrame con precios. El usuario dice: "{command}"
    
    Interpreta el comando y devuelve SOLO el código Python para modificar el DataFrame.
    Usa 'df' como variable del DataFrame.
    
    Ejemplos:
    - "aumenta todo 10%" -> df['precio'] = df['precio'] * 1.10
    - "cambia el precio de fila 1 a 500" -> df.loc[0, 'precio'] = 500
    - "descuenta 20% a productos menores a 100" -> df.loc[df['precio'] < 100, 'precio'] *= 0.80
    
    SOLO devuelve código Python ejecutable:
    """
    
    # Aquí integrarías OpenAI API
    # Por simplicidad, manejo básico de comandos
    if "aumenta" in command.lower() or "incrementa" in command.lower():
        numbers = re.findall(r'\d+', command)
        if numbers:
            percentage = float(numbers[0]) / 100
            return f"df['precio'] = df['precio'] * {1 + percentage}"
    
    elif "descuenta" in command.lower() or "reduce" in command.lower():
        numbers = re.findall(r'\d+', command)
        if numbers:
            percentage = float(numbers[0]) / 100
            return f"df['precio'] = df['precio'] * {1 - percentage}"
    
    return "# Comando no reconocido"

# UI Principal
st.title("Cambio de Precios con IA")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Cargar Archivo")
    uploaded_file = st.file_uploader(
        "Sube PDF, Excel o Imagen", 
        type=['pdf', 'xlsx', 'xls', 'png', 'jpg', 'jpeg']
    )
    
    if uploaded_file:
        with st.spinner("Procesando..."):
            st.session_state.df = process_uploaded_file(uploaded_file)
    
    # Control por voz
    st.subheader("Control por Voz")
    if VOICE_AVAILABLE:
        if st.button("🎤 Hablar"):
            voice_command = speech_to_text()
            st.write(f"Comando: {voice_command}")
            
            if st.session_state.df is not None:
                code = process_price_command(voice_command, st.session_state.df)
                try:
                    exec(code, {'df': st.session_state.df})
                    st.success("Comando ejecutado")
                    text_to_speech("Precios actualizados")
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.info("Control por voz no disponible en Streamlit Cloud")

with col2:
    st.subheader("Chat de Comandos")
    
    # Chat input
    user_input = st.chat_input("Escribe comando para cambiar precios")
    
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        if st.session_state.df is not None:
            code = process_price_command(user_input, st.session_state.df)
            
            try:
                exec(code, {'df': st.session_state.df})
                response = "Precios actualizados correctamente"
                st.session_state.chat_history.append({"role": "assistant", "content": response})
            except Exception as e:
                response = f"Error ejecutando comando: {e}"
                st.session_state.chat_history.append({"role": "assistant", "content": response})
        else:
            response = "Primero carga un archivo con precios"
            st.session_state.chat_history.append({"role": "assistant", "content": response})
    
    # Mostrar chat
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# Mostrar DataFrame
if st.session_state.df is not None:
    st.subheader("Precios Actuales")
    st.dataframe(st.session_state.df, use_container_width=True)
    
    # Descargar DataFrame modificado
    csv = st.session_state.df.to_csv(index=False)
    st.download_button(
        label="Descargar CSV",
        data=csv,
        file_name="precios_modificados.csv",
        mime="text/csv"
    )

# Comandos rápidos
st.sidebar.subheader("Comandos Rápidos")
if st.sidebar.button("Aumentar 10%"):
    if st.session_state.df is not None:
        st.session_state.df['precio'] = st.session_state.df['precio'] * 1.10

if st.sidebar.button("Descuento 15%"):
    if st.session_state.df is not None:
        st.session_state.df['precio'] = st.session_state.df['precio'] * 0.85

if st.sidebar.button("Redondear precios"):
    if st.session_state.df is not None:
        st.session_state.df['precio'] = st.session_state.df['precio'].round(2)