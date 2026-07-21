import os
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.async_api import async_playwright
import requests

# 1. LISTA DE FUENTES A MONITOREAR
PAGINAS = [
    # CFE
    {"nombre": "CFE - Elección de Horas", "url": "https://www.cfe.edu.uy/index.php/funcionarios/docentes/eleccion-de-horas"},
    {"nombre": "CFE - Concursos Portal", "url": "https://concursos.cfe.edu.uy/ConcursosCFE/servlet/com.si.recsel.inicio"},
    {"nombre": "CFE - Principal", "url": "https://www.cfe.edu.uy/"},
    {"nombre": "CFE - Llamados Abreviados", "url": "https://www.cfe.edu.uy/index.php/funcionarios/docentes/llamados-abreviados"},
    
    # UTU
    {"nombre": "UTU - Concursos y Llamados", "url": "https://www.utu.edu.uy/funcionarios/concursos-y-llamados/"},
    
    # ANII
    {"nombre": "ANII - Contrataciones", "url": "https://anii.org.uy/institucional/contrataciones/"},
    
    # UCU
    {"nombre": "UCU - Trabaje con Nosotros", "url": "https://www.ucu.edu.uy/categoria/Trabaje-con-nosotros-417"},
    {"nombre": "UCU - Llamados Docentes", "url": "https://www.ucu.edu.uy/categoria/Llamados-docentes-455"},
    
    # ORT
    {"nombre": "ORT - Oportunidades Laborales", "url": "https://www.ort.edu.uy/oportunidades-laborales"},
    
    # Computrabajo
    {"nombre": "Computrabajo - Montevideo", "url": "https://uy.computrabajo.com/empleos-en-montevideo"}
]

# --- 2. EXTRAER CONTENIDO DE TODAS LAS PÁGINAS ---
async def extraer_contenido():
    resultados = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for sitio in PAGINAS:
            print(f"Extrayendo: {sitio['nombre']}...")
            try:
                await page.goto(sitio['url'], wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                
                texto_pagina = await page.inner_text("body")
                texto_limpio = " ".join(texto_pagina.split())[:3000] 
                
                resultados.append(f"=== FUENTE: {sitio['nombre']} ===\nURL: {sitio['url']}\nCONTENIDO EXTRAÍDO:\n{texto_limpio}\n\n")
            except Exception as e:
                print(f"Error al procesar {sitio['nombre']}: {e}")
                resultados.append(f"=== FUENTE: {sitio['nombre']} ===\nURL: {sitio['url']}\n[No se pudo cargar la página]\n\n")

        await browser.close()
        
    return "\n".join(resultados)

# --- 3. ANALIZAR Y FILTRAR CON xAI (Grok) ---
def analizar_con_ia(texto):
    print("Analizando contenido con xAI (Grok)...")
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    texto_recortado = texto[:15000] if len(texto) > 15000 else texto
    
    prompt = f"""
    Eres un asistente experto en recursos humanos. 
    A continuación te paso un texto extraído de varias páginas de empleo en Uruguay.
    Por favor, resume las ofertas de trabajo más relevantes, indicando cargo, institución y enlace si está disponible.
    
    TEXTO:
    {texto_recortado}
    """
    
    data = {
        "model": "grok-2-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error detallado al analizar con IA: {e}")
        if hasattr(response, 'text'):
            print(f"Respuesta del servidor: {response.text}")
        return "Hubo un error al generar el resumen de las ofertas."

# --- 4. FUNCIÓN PARA ENVIAR CORREO ---
def enviar_email(resumen):
    print("Enviando correo electrónico...")
    remitente = os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASS')
    destinatario = os.environ.get('EMAIL_TO')

    if not remitente or not password or not destinatario:
        print("Error: Faltan credenciales de correo en los Secrets de GitHub.")
        return

    msg = MIMEMultipart()
    msg['From'] = remitente
    msg['To'] = destinatario
    msg['Subject'] = "Resumen Diario de Empleos - Uruguay"

    msg.attach(MIMEText(resumen, 'plain', 'utf-8'))

    try:
        # Configuración por defecto para Gmail (puerto 465 SSL)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(remitente, password)
            server.sendmail(remitente, destinatario, msg.as_string())
        print("¡Email con el resumen enviado con éxito!")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")

# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    print("Iniciando escaneo de páginas laborales...")
    contenido_extraido = asyncio.run(extraer_contenido())
    
    print("Analizando contenido con Grok...")
    resumen = analizar_con_ia(contenido_extraido)
    
    print("\n--- RESUMEN GENERADO ---")
    print(resumen)
    
    enviar_email(resumen)
