import os
import smtplib
import asyncio
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from playwright.async_api import async_playwright
from google import genai
from google.genai import types, errors
from markdown_pdf import MarkdownPdf, Section

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

# --- 3. ANALIZAR Y FILTRAR CON GOOGLE GEMINI ---
def analizar_con_ia(texto):
    print("Analizando contenido con Google Gemini...")

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("Error: Falta la GEMINI_API_KEY en los Secrets de GitHub.")
        return "Hubo un error al generar el resumen de las ofertas."

    client = genai.Client(api_key=api_key)

    prompt = f"""
    Eres un asistente experto en recursos humanos. 
    A continuación te paso un texto extraído de varias páginas de empleo en Uruguay.
    Por favor, resume las ofertas de trabajo más relevantes, indicando cargo, institución y enlace si está disponible.

    Formateá la respuesta en Markdown: un encabezado de nivel 2 (##) por institución, y cada
    oferta como un ítem de lista con el cargo en negrita. Si no hay ofertas nuevas o relevantes,
    decilo directamente en una sola línea.
    
    TEXTO:
    {texto}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            )
        )
        return response.text
    except errors.APIError as e:
        print(f"Error de la API de Gemini: {e.code} - {e.message}")
        return "Hubo un error al generar el resumen de las ofertas."
    except Exception as e:
        print(f"Error inesperado al analizar con IA: {e}")
        return "Hubo un error al generar el resumen de las ofertas."

# --- 4. CONVERTIR EL RESUMEN (MARKDOWN) A PDF ---
def markdown_a_pdf(texto_markdown, ruta_pdf):
    """Convierte un texto en formato Markdown a un archivo PDF prolijo."""
    css = """
    body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #222222; }
    h1, h2, h3 { color: #111111; }
    a { color: #1155cc; }
    """
    fecha = datetime.now().strftime('%d/%m/%Y')
    contenido = f"# Resumen Diario de Empleos - Uruguay\n*{fecha}*\n\n{texto_markdown}"

    pdf = MarkdownPdf(toc_level=0)
    pdf.add_section(Section(contenido, toc=False), user_css=css)
    pdf.meta["title"] = "Resumen Diario de Empleos - Uruguay"
    pdf.save(ruta_pdf)

# --- 5. FUNCIÓN PARA ENVIAR CORREO ---
def enviar_email(resumen, formato_pdf=False):
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

    if formato_pdf:
        try:
            nombre_pdf = f"resumen_empleos_{datetime.now().strftime('%Y-%m-%d')}.pdf"
            ruta_pdf = f"/tmp/{nombre_pdf}"
            markdown_a_pdf(resumen, ruta_pdf)

            with open(ruta_pdf, 'rb') as f:
                adjunto = MIMEApplication(f.read(), _subtype='pdf')
            adjunto.add_header('Content-Disposition', 'attachment', filename=nombre_pdf)
            msg.attach(adjunto)
            print(f"PDF generado y adjuntado: {nombre_pdf}")
        except Exception as e:
            print(f"No se pudo generar el PDF, se envía el correo solo con el texto: {e}")

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
    
    print("Analizando contenido con Gemini...")
    resumen = analizar_con_ia(contenido_extraido)
    
    print("\n--- RESUMEN GENERADO ---")
    print(resumen)
    
    enviar_email(resumen, formato_pdf=True)