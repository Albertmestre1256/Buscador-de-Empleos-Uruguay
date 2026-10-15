import os
import smtplib
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from playwright.async_api import async_playwright
from google import genai
from google.genai import types, errors
from markdown_pdf import MarkdownPdf, Section
from resilience import generar_con_reintentos, informe_respaldo
from configuracion import cargar_perfil, cargar_sitios, construir_prompt

# Las fuentes se editan en sitios.json; el perfil se edita en perfil.md.

# --- 2. EXTRAER CONTENIDO DE TODAS LAS PÁGINAS ---
async def extraer_contenido(sitios=None):
    resultados = []
    sitios = cargar_sitios() if sitios is None else sitios
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for sitio in sitios:
            print(f"Extrayendo: {sitio['nombre']}...")
            try:
                if sitio.get('esperar_respuesta'):
                    async with page.expect_response(
                        lambda r: sitio['esperar_respuesta'] in r.url,
                        timeout=60000
                    ) as carga:
                        respuesta = await page.goto(sitio['url'], wait_until="domcontentloaded", timeout=30000)
                    datos = await carga.value
                    if datos.status >= 400:
                        raise RuntimeError(f"La carga de llamados devolvió HTTP {datos.status}")
                    await asyncio.wait_for(datos.body(), timeout=30)
                else:
                    respuesta = await page.goto(sitio['url'], wait_until="domcontentloaded", timeout=30000)
                if respuesta is not None and respuesta.status >= 400:
                    raise RuntimeError(f"HTTP {respuesta.status}")
                await page.wait_for_timeout(2000)

                contenido = await page.evaluate("""(selector) => {
                    const original = selector ? document.querySelector(selector)
                        : document.querySelector('main, [role="main"], #content, #contenido') || document.body;
                    if (!original) throw new Error('No se encontró el selector configurado');
                    const copia = original.cloneNode(true);
                    copia.querySelectorAll('nav, header, footer, script, style, noscript').forEach(n => n.remove());
                    return {
                        texto: copia.textContent,
                        enlaces: Array.from(copia.querySelectorAll('a[href]')).map(a => ({
                            texto: a.textContent.trim(),
                            url: new URL(a.getAttribute('href'), document.baseURI).href
                        })).filter(a => a.texto && /^https?:/.test(a.url))
                    };
                }""", sitio.get('selector'))
                texto_limpio = " ".join(contenido['texto'].split())
                if not texto_limpio:
                    raise RuntimeError("Página sin contenido extraíble")
                truncado = len(texto_limpio) > 8000
                enlaces = list(dict.fromkeys(f"{a['texto'][:180]}: {a['url']}" for a in contenido['enlaces']))
                resultados.append(
                    f"=== FUENTE: {sitio['nombre']} ===\nURL: {page.url}\n"
                    f"CONTENIDO EXTRAÍDO{' (truncado a 8000 caracteres)' if truncado else ''}:\n"
                    f"{texto_limpio[:8000]}\nENLACES (hasta 60):\n" + "\n".join(enlaces[:60]) + "\n"
                )
            except Exception as e:
                print(f"Error al procesar {sitio['nombre']}: {e}")
                resultados.append(f"=== FUENTE: {sitio['nombre']} ===\nURL: {sitio['url']}\n[No se pudo cargar la página]\n\n")

        await browser.close()
        
    return "\n".join(resultados)

# --- 3. ANALIZAR Y FILTRAR CON GOOGLE GEMINI ---
def analizar_con_ia(texto, perfil):
    print("Analizando contenido con Google Gemini...")

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("Error: Falta la GEMINI_API_KEY en los Secrets de GitHub.")
        print("::warning::Informe de respaldo: falta GEMINI_API_KEY.")
        return informe_respaldo(texto, "No se configuró la clave de Gemini.")

    prompt = construir_prompt(texto, perfil, datetime.now(ZoneInfo("America/Montevideo")).date())

    try:
        client = genai.Client(api_key=api_key)
        def generar():
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            return response.text
        return generar_con_reintentos(generar)
    except errors.APIError as e:
        print(f"::warning::Gemini falló (HTTP {e.code}); se genera informe de respaldo.")
        motivo = ("Gemini alcanzó un límite de cuota (HTTP 429)." if e.code == 429
                  else f"Gemini no pudo generar el análisis (HTTP {e.code}).")
        return informe_respaldo(texto, motivo)
    except Exception as e:
        print(f"::warning::Falló el análisis ({type(e).__name__}); se genera informe de respaldo.")
        return informe_respaldo(texto, "No se pudo completar el análisis de Gemini.")

# --- 4. CONVERTIR EL RESUMEN (MARKDOWN) A PDF ---
def markdown_a_pdf(texto_markdown, ruta_pdf):
    """Convierte un texto en formato Markdown a un archivo PDF prolijo."""
    css = """
    body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #222222; }
    h1, h2, h3 { color: #111111; }
    a { color: #1155cc; }
    """
    fecha = datetime.now(ZoneInfo("America/Montevideo")).strftime('%d/%m/%Y')
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
            nombre_pdf = f"resumen_empleos_{datetime.now(ZoneInfo('America/Montevideo')).strftime('%Y-%m-%d')}.pdf"
            with TemporaryDirectory() as carpeta:
                ruta_pdf = str(Path(carpeta) / nombre_pdf)
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
def main():
    parser = argparse.ArgumentParser(description="Buscar llamados y recomendar según un perfil Markdown.")
    parser.add_argument("--perfil", help="Ruta a otro perfil .md (por defecto: perfil.md).")
    parser.add_argument("--sitios", help="Ruta a otra lista JSON (por defecto: sitios.json).")
    parser.add_argument("--sin-email", action="store_true", help="Guardar el informe sin enviar correo.")
    parser.add_argument("--sin-ia", action="store_true", help="Extraer fuentes sin consumir la API de Gemini.")
    args = parser.parse_args()
    perfil = cargar_perfil(args.perfil)
    sitios = cargar_sitios(args.sitios)
    print("Iniciando escaneo de páginas laborales...")
    contenido_extraido = asyncio.run(extraer_contenido(sitios))
    
    print("Analizando contenido con Gemini...")
    resumen = (informe_respaldo(contenido_extraido, "Análisis de IA desactivado por --sin-ia.")
               if args.sin_ia else analizar_con_ia(contenido_extraido, perfil))
    
    print("\n--- RESUMEN GENERADO ---")
    print(resumen)
    
    salida = Path("salida")
    salida.mkdir(exist_ok=True)
    (salida / "informe.md").write_text(resumen, encoding="utf-8")
    if not args.sin_email:
        enviar_email(resumen, formato_pdf=True)


if __name__ == "__main__":
    main()
