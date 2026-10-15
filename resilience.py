"""Recuperación acotada de fallos del proveedor, sin dependencias externas."""
import time


def generar_con_reintentos(generar, dormir=time.sleep):
    """Hasta tres llamadas; errores permanentes no consumen más cuota."""
    for intento in range(3):
        try:
            texto = generar()
            if not texto or not texto.strip():
                raise ValueError("Gemini devolvió una respuesta vacía")
            return texto
        except Exception as error:
            codigo = getattr(error, "code", None)
            if codigo not in (429, 500, 502, 503, 504) or intento == 2:
                raise
            espera = 15 * (2 ** intento)
            print(f"Gemini no disponible (HTTP {codigo}); reintento en {espera}s.")
            dormir(espera)


def informe_respaldo(texto, motivo):
    return (
        "## Informe de respaldo — sin análisis de IA\n\n"
        f"{motivo}\n\n"
        "El contenido siguiente fue extraído de las fuentes y no fue validado "
        "ni filtrado por IA. Puede incluir menús, avisos antiguos y páginas "
        "sin ofertas. Verificá requisitos y vigencia en cada enlace.\n\n"
        "```text\n" + texto.replace("```", "'''") + "\n```\n"
    )
