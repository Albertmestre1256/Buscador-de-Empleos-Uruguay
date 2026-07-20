import os
import smtplib
import asyncio
from email.mime.text import MIMEText
from playwright.async_api import async_playwright
from google import genai

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

# --- 3. ANALIZAR Y FILTRAR CON GEMINI ---
def analizar_con_gemini(texto_completo):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "Falta la API Key de Gemini."
        
    # Inicializar el cliente de Gemini
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Eres un asistente personal experto en búsqueda de empleo y llamados docentes/laborales en Uruguay.
    A continuación tienes el contenido textual extraído hoy de varias páginas de instituciones (CFE, UTU, ANII, UCU, ORT, Computrabajo):

    {texto_completo}

    INSTRUCCIONES:
    1. Revisa cada sección e identifica si hay **nuevos llamados, vacantes de empleo, concursos o oportunidades laborales** publicados.
    2. Si encuentras llamadas u ofertas, organízalas por institución con:
       - Título de la vacante / llamado
       - Breve descripción o requisitos si están disponibles
       - El enlace directo a la página donde se encontró (URL proporcionada en el texto)
    3. Si alguna página no muestra llamados claros o no tuvo cambios/vacantes, omítela del reporte.
    4. Si en **ninguna** de las páginas hay ofertas relevantes, responde exactamente: "No se encontraron nuevos llamados ni ofertas de interés hoy."
    5. Formatea la respuesta de manera muy clara, profesional y fácil de leer por correo electrónico.
    """
    
    # Generar contenido usando Gemini 2.5 Flash
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    
    return response.text

# --- 4. ENVÍO DE EMAIL ---
def enviar_email(mensaje):
    email_emisor = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASS")
    email_receptor = os.environ.get("EMAIL_TO")
    
    if not email_emisor or not password or not email_receptor:
        print("Faltan variables de entorno para el envío de correo.")
        return

    msg = MIMEText(mensaje, 'plain', 'utf-8')
    msg['Subject'] = '📌 Resumen Diario: Llamados y Empleos (CFE, UTU, UCU, etc.)'
    msg['From'] = email_emisor
    msg['To'] = email_receptor
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(email_emisor, password)
            server.sendmail(email_emisor, email_receptor, msg.as_string())
        print("¡Email con el resumen enviado con éxito!")
    except Exception as e:
        print(f"Error al enviar email: {e}")

# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    print("Iniciando escaneo de páginas laborales...")
    contenido_extraido = asyncio.run(extraer_contenido())
    
    print("Analizando contenido con Gemini...")
    resumen = analizar_con_gemini(contenido_extraido)
    
    print("\n--- RESUMEN GENERADO ---")
    print(resumen)
    
    if "No se encontraron nuevos llamados" not in resumen:
        enviar_email(resumen)
    else:
        print("No se enviará correo hoy ya que no hubo novedades relevantes.")
