# Buscador de Empleos Uruguay

Esta es una nueva versión retocada del buscador original. Usé OpenAI Codex para
ampliar su funcionamiento: incorporar más fuentes de empleo público, agregar
recomendaciones según un perfil editable y mejorar la recuperación ante fallos
de Gemini.

Recorre sitios de empleo, reúne el contenido disponible y le pide a Google Gemini
un informe con **llamados encontrados** y **recomendaciones según un perfil**.
Guarda el informe en `salida/informe.md` y, por defecto, lo envía por Gmail con un
PDF adjunto. No realiza postulaciones.

## Archivos que podés editar

| Archivo | Para qué sirve |
| --- | --- |
| `perfil.md` | Describe el objetivo, formación, experiencia y preferencias de quien busca empleo. |
| `sitios.json` | Lista de fuentes; permite agregar, desactivar o eliminar sitios sin tocar Python. |
| `.github/workflows/ejecucion.yml` | Horario y ejecución automática en GitHub Actions. |
| `configuracion.py` | Validación y reglas con las que la IA arma el informe. |

## Configurar el perfil y adecuar los llamados

1. Abrí `perfil.md` en GitHub y presioná el lápiz para editar.
2. Reemplazá el ejemplo de **analista de datos comerciales junior** con información
   verdadera: puestos deseados, formación y su estado, tareas y años de experiencia,
   herramientas y nivel, idiomas, ubicación, modalidad, disponibilidad y exclusiones.
3. Guardá el cambio en la rama que vayas a ejecutar. El ejemplo trae campos
   **por completar**: no describe automáticamente tu trayectoria.

Para buscar otro perfil (docencia, administración, investigación, etc.), cambiá
estos apartados y adaptá las fuentes en `sitios.json`. No necesitás cambiar código.
Las recomendaciones se generan con el archivo completo en cada ejecución.
Una preferencia de cargo no demuestra que cumplas sus requisitos.

La IA muestra los llamados identificados aunque no coincidan con tu objetivo;
después recomienda los de mayor encaje, indicando motivos, brechas y requisitos
pendientes de verificar. Los vencidos o cerrados no deben figurar como recomendaciones.
Si faltan datos decisivos, la recomendación debe quedar condicionada.

**Privacidad:** este repositorio es público. Lo que guardes en `perfil.md` será
visible públicamente y su historial puede conservarlo. No incluyas cédula,
dirección, contraseñas ni información sensible. El perfil y el contenido extraído
se envían a Google Gemini para analizarlos. Para uso local podés crear
`perfil.local.md` (ignorado por Git) y pasar `--perfil perfil.local.md`.
El programa no carga automáticamente archivos `.env`.

## Sitios incluidos

Se mantienen las fuentes originales de CFE, UTU, ANII, UCU, ORT y Computrabajo,
y se agregan estos portales públicos:

- [Uruguay Concursa: búsqueda de llamados](https://uruguayconcursa.gub.uy/search).
- [BPS: concursos externos vigentes](https://www.bps.gub.uy/63/concursos-externos-vigentes.html).
- [OSE: concursos externos](https://www.ose.com.uy/oportunidades-laborales/concursos-externos).
- [Intendencia de Montevideo: convocatorias y llamados](https://montevideo.gub.uy/noticias/convocatorias-y-llamados-0?page=0).
- [Udelar: concursos y llamados](https://www.concursos.udelar.edu.uy/index.php?script=27).

### Agregar, modificar o eliminar sitios

Editá `sitios.json`. Cada entrada tiene esta forma:

```json
{
  "nombre": "Organismo - Llamados",
  "url": "https://organismo.gub.uy/llamados",
  "activo": true
}
```

- **Agregar:** copiá una entrada dentro de la lista y cambiá nombre y URL por la
  página real del organismo. Separá las entradas con comas, sin coma después de la última.
- **Cambiar el tipo de llamados:** apuntá la URL a la sección correspondiente,
  por ejemplo concursos externos o una búsqueda filtrada que permita ese portal.
- **Desactivar temporalmente:** cambiá `"activo": true` por `"activo": false`.
- **Eliminar:** borrá el objeto completo y ajustá las comas de la lista.

Usá URLs públicas que abran directamente el listado. Un menú de inicio puede
no contener las ofertas. Para una página con mucho menú podés agregar el campo
opcional `"selector": "#listado"`, reemplazándolo por un selector CSS real del
contenedor. Si no existe, el sitio se informa como fallido. Sin selector se intenta
usar el contenido principal y, si no existe, el cuerpo de la página.

Uruguay Concursa tiene además `"esperar_respuesta": "/api-backend/llamados/find"`:
el programa espera hasta 60 segundos la respuesta que carga el listado, para no
confundir un encabezado todavía vacío con ausencia de llamados. Si el portal
cambia esa ruta habrá que actualizarla; un timeout se informa como fuente fallida.

Tiene que quedar al menos un sitio activo. Probá cualquier cambio con
`python main.py --sin-ia --sin-email` antes de consumir la API.

## Usar desde GitHub Actions

1. En tu copia del repositorio, editá `perfil.md` y `sitios.json`.
2. En **Settings → Secrets and variables → Actions → Secrets**, configurá:

   | Secret | Contenido |
   | --- | --- |
   | `GEMINI_API_KEY` | Clave de la API de Gemini obtenida en Google AI Studio. |
   | `EMAIL_USER` | Cuenta Gmail que envía el informe. |
   | `EMAIL_PASS` | Contraseña de aplicación de Google, no la contraseña habitual. |
   | `EMAIL_TO` | Dirección que recibe el informe. |

3. Opcional: en **Variables**, creá `GEMINI_MODEL` con el identificador de un
   modelo disponible para tu clave. El valor por defecto es `gemini-3.6-flash`.
4. En **Actions → Buscador de Empleos Uruguay → Run workflow**, seleccioná la
   rama que contiene estos cambios y ejecutá. Esto **envía un correo** al destinatario.

La ejecución programada usa la rama predeterminada. El cron actual es `0 11 * * *`:
todos los días a las 11:00 UTC, equivalentes a las 08:00 en Uruguay (UTC−3).
GitHub puede ejecutarlo con demora. Para cambiarlo editá `schedule` en
`.github/workflows/ejecucion.yml`; los horarios cron están en UTC.

## Ejecutar localmente

Requiere Python 3.10 o superior. Desde la carpeta del repositorio:

```bash
python -m venv .venv
```

Activá el entorno: en PowerShell, `.\.venv\Scripts\Activate.ps1`; en Linux/macOS,
`source .venv/bin/activate`. Después:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

En Linux puede ser necesario `python -m playwright install --with-deps chromium`.
Primero probá la extracción sin IA ni correos:

```bash
python main.py --sin-ia --sin-email
```

Para analizar sin enviar correo, definí `GEMINI_API_KEY` en el entorno y ejecutá:

```bash
python main.py --perfil perfil.md --sin-email
```

En PowerShell definís una variable con `$env:GEMINI_API_KEY = "tu-clave"`; en
Linux/macOS, `export GEMINI_API_KEY="tu-clave"`. No guardes la clave en el repo.
Para enviar correo, configurá también las tres variables `EMAIL_*` y ejecutá
`python main.py`.

Podés seleccionar otros archivos:

```bash
python main.py --perfil perfil.local.md --sitios mis-sitios.json --sin-email
```

El informe se guarda
en `salida/informe.md`, relativo a la carpeta desde la que ejecutaste el comando.
`perfil.md` y `sitios.json` se buscan junto al programa cuando no pasás rutas.

## Si falla Gemini o faltan ofertas

Se reintentan errores HTTP 429, 500, 502, 503 y 504 con esperas de 15 y 30 segundos
(hasta tres intentos de aplicación; el SDK puede aplicar sus propios reintentos).
Reintentar no aumenta la cuota disponible. Si falta la clave, la respuesta está
vacía o el análisis sigue fallando, se genera un **informe de respaldo sin IA**
con el contenido recogido y sus fuentes. No contiene recomendaciones personalizadas.
Los registros de Actions muestran una advertencia cuando se usa ese respaldo.

La extracción está limitada a **8000 caracteres y 60 enlaces por sitio**, con
una espera de 2 segundos para contenido dinámico (además de la espera específica
de Uruguay Concursa). No recorre automáticamente
la paginación, no abre cada oferta ni lee las bases PDF. Algunos portales pueden
bloquear la automatización o requerir más espera. Un sitio fallido no significa
que no tenga llamados. Revisá la cobertura del informe y los registros de Actions.
La IA no garantiza detectar todas las ofertas ni acertar la elegibilidad: revisá
siempre las bases, fechas y requisitos en el portal oficial.

No se guarda historial de ofertas: un llamado repetido al día siguiente no es
necesariamente nuevo. Agregar fuentes aumenta el contenido enviado a Gemini y
puede afectar los límites de tokens de tu plan; desactivá las que no uses.

## Verificar cambios

```bash
python -m unittest discover -v
```

Las pruebas usan respuestas simuladas para comprobar recuperación ante errores,
configuración, incorporación del perfil y del contenido al análisis. No consumen
cuota de Gemini ni envían correos.
