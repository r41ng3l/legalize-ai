import os
import asyncio
import subprocess
import yaml
import logging
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.events import Event          # <--- NUEVO IMPORT REQUERIDO
from google.genai import types

logger = logging.getLogger(__name__)

# Ruta absoluta al repositorio de leyes
LEGAL_REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "legalize-es", "spain"))

# ==========================================
# 1. HERRAMIENTAS (TOOLS) OPTIMIZADAS
# ==========================================
def buscar_leyes_ripgrep(palabras_clave: str) -> str:
    """Busca palabras clave en el repositorio y devuelve una lista de los documentos más relevantes.
    Acepta términos separados por comas (ej. 'interrupción voluntaria del embarazo, aborto').
    Devuelve el TÍTULO OFICIAL, el recuento de coincidencias y el nombre del archivo.
    """
    if not os.path.exists(LEGAL_REPO_PATH):
        return f"Error: No se encuentra el directorio de leyes en {LEGAL_REPO_PATH}."

    terminos =[t.strip().strip('"').strip("'") for t in palabras_clave.split(',') if t.strip()]
    if not terminos:
        return "Error: no se proporcionaron palabras clave."

    # Usamos -c para que ripgrep solo devuelva el conteo por archivo
    patrones = " ".join(f'-e "{t}"' for t in terminos)
    cmd_count = f'rg -i {patrones} -c "{LEGAL_REPO_PATH}" 2>/dev/null'
    logger.info(f"[buscar_leyes] Ejecutando: {cmd_count}")
    
    try:
        count_output = subprocess.check_output(cmd_count, shell=True, text=True)
        # Parsear output: "ruta/al/archivo:numero_coincidencias"
        resultados =[]
        for linea in count_output.strip().split('\n'):
            if ':' in linea:
                ruta, recuento_str = linea.rsplit(':', 1)
                try:
                    resultados.append((ruta, int(recuento_str)))
                except ValueError:
                    continue
                    
        # Ordenar por mayor número de coincidencias y tomar los 10 mejores
        resultados_ordenados = sorted(resultados, key=lambda x: x[1], reverse=True)[:10]
    except subprocess.CalledProcessError:
        return "No se encontraron coincidencias para esas palabras clave."

    if not resultados_ordenados:
        return "No se encontraron resultados."

    respuesta = "DOCUMENTOS MÁS RELEVANTES ENCONTRADOS:\n\n"
    
    # Extraemos el título leyendo solo el frontmatter de los top 10 archivos
    for ruta, hits in resultados_ordenados:
        archivo_boe = os.path.basename(ruta)
        titulo = "Título desconocido"
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                contenido = f.read(2000) # Leer solo los primeros 2000 chars para el YAML
                partes = contenido.split('---')
                if len(partes) >= 3:
                    metadatos = yaml.safe_load(partes[1])
                    titulo = metadatos.get('titulo', 'Título desconocido')
        except Exception as e:
            logger.warning(f"Error leyendo metadatos de {archivo_boe}: {e}")
            
        respuesta += f"- Archivo: `{archivo_boe}` | Coincidencias: {hits} | Título: {titulo}\n"

    respuesta += "\nINSTRUCCIÓN PARA EL AGENTE: Si alguno de estos títulos parece responder a la pregunta del usuario, usa la herramienta 'leer_archivo_boe' pasando el nombre exacto del archivo (ej. BOE-A-2010-3514.md) para leer su articulado."
    
    return respuesta


def leer_archivo_boe(archivo_boe: str) -> str:
    """Lee el contenido completo de un archivo BOE del repositorio.
    DEBES usar esta herramienta con un nombre de archivo válido (ej. BOE-A-2010-3514.md) 
    obtenido previamente en la búsqueda para poder leer los artículos exactos.
    """
    archivo_boe = os.path.basename(archivo_boe)
    ruta = os.path.join(LEGAL_REPO_PATH, archivo_boe)

    if not os.path.exists(ruta):
        candidatos =[f for f in os.listdir(LEGAL_REPO_PATH) if archivo_boe.lower() in f.lower()]
        if candidatos:
            ruta = os.path.join(LEGAL_REPO_PATH, candidatos[0])
            archivo_boe = candidatos[0]
        else:
            return f"Error: No se encontró el archivo '{archivo_boe}'."

    logger.info(f"[leer_archivo_boe] Leyendo: {ruta}")

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    partes = contenido.split('---')
    titulo_ley, url_boe = "Ley desconocida", "#"
    if len(partes) >= 3:
        try:
            metadatos = yaml.safe_load(partes[1])
            titulo_ley = metadatos.get('titulo', 'Ley desconocida')
            url_boe = metadatos.get('fuente', '#')
        except yaml.YAMLError:
            pass

    cuerpo = partes[2] if len(partes) >= 3 else contenido
    
    cabecera = (
        f"--- METADATOS DEL DOCUMENTO ---\n"
        f"Título: {titulo_ley}\n"
        f"Archivo: {archivo_boe}\n"
        f"URL Oficial BOE: {url_boe}\n\n"
        f"--- CONTENIDO DE LA LEY ---\n"
    )
    
    return cabecera + cuerpo[:200000]


# ==========================================
# 2. LÓGICA ASYNC DEL AGENTE ÚNICO
# ==========================================
async def ejecutar_pipeline_legal(historial: List[dict], model: str) -> str:
    """Ejecuta el agente con el historial completo de mensajes."""

    # Un solo Agente Experto que itera (ReAct: Reason + Act)
    abogado_experto = LlmAgent(
        model=model,
        name="AbogadoExperto",
        description="Agente legal experto en el BOE español que busca, lee leyes y redacta respuestas precisas.",
        instruction=(
            "Eres un abogado experto en legislación española. Tu objetivo es dar respuestas precisas "
            "basadas ÚNICAMENTE en las leyes del repositorio local (BOE).\n\n"
            "PROCESO OBLIGATORIO:\n"
            "1. Analiza la consulta y extrae conceptos clave.\n"
            "2. Usa OBLIGATORIAMENTE la herramienta `buscar_leyes_ripgrep` con esos términos para obtener una lista de leyes (títulos y archivos).\n"
            "3. Revisa la lista devuelta. Identifica qué ley o leyes tienen más probabilidad de contener la respuesta.\n"
            "4. Usa OBLIGATORIAMENTE la herramienta `leer_archivo_boe` pasándole el nombre del archivo (ej. 'BOE-A-2010-3514.md') para leer su contenido real.\n"
            "5. Busca en el texto que te devuelve el artículo exacto que responde a la pregunta.\n\n"
            "REGLAS DE FORMATO PARA LA RESPUESTA FINAL:\n"
            "- DEBES responder directamente a la pregunta del usuario. No le digas 'he encontrado estos archivos'. Dale la respuesta legal.\n"
            "- DEBES citar siempre la ley y el artículo exacto de forma clara.\n"
            "- DEBES incluir enlaces Markdown a la fuente oficial del BOE que extraigas de los metadatos de la ley.\n"
            "- Formato de cita requerido: 'Según el [Artículo X de la Ley Y](URL_OFICIAL), se establece que...'\n"
            "- Si tras leer el archivo la respuesta no está ahí, inténtalo con otro archivo de tu lista de resultados."
        ),
        tools=[buscar_leyes_ripgrep, leer_archivo_boe],
    )

    runner = InMemoryRunner(agent=abogado_experto, app_name="legalize-ai")
    session = await runner.session_service.create_session(
        app_name="legalize-ai",
        user_id="webui_user",
    )

    # Inyectar historial completo (¡CÓDIGO CORREGIDO!)
    for msg in historial[:-1]:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if role in ('user', 'assistant') and content:
            adk_role = 'user' if role == 'user' else 'model'
            
            # Instanciamos el objeto Event correctamente
            author_val = 'user' if adk_role == 'user' else abogado_experto.name
            evento_historico = Event(
                author=author_val,
                content=types.Content(
                    role=adk_role,
                    parts=[types.Part(text=content)],
                )
            )
            
            # Lo inyectamos usando solo session y el objeto event
            await runner.session_service.append_event(session, evento_historico)

    # Mensaje actual
    ultimo_mensaje = historial[-1].get('content', '')
    mensaje = types.Content(
        role="user",
        parts=[types.Part(text=ultimo_mensaje)],
    )

    respuesta_final = ""
    async for event in runner.run_async(
        user_id="webui_user",
        session_id=session.id,
        new_message=mensaje,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            respuesta_final = event.content.parts[0].text
            break

    return respuesta_final or "No se pudo obtener una respuesta del agente legal."


# ==========================================
# 3. CLASE PIPELINE PARA OPEN WEBUI
# ==========================================
class Pipeline:
    class Valves(BaseModel):
        GEMINI_API_KEY: str = ""
        OPENAI_API_KEY: str = ""
        ANTHROPIC_API_KEY: str = ""
        MODEL_NAME: str = ""

    def __init__(self):
        self.name = "Asistente Legalize (BOE)"
        self.valves = self.Valves(
            GEMINI_API_KEY=os.getenv("GEMINI_API_KEY", ""),
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
            ANTHROPIC_API_KEY=os.getenv("ANTHROPIC_API_KEY", ""),
            MODEL_NAME=os.getenv("MODEL_NAME", ""),
        )

    async def on_startup(self):
        print(f"[{self.name}] Inicializando agentes y conectando con {LEGAL_REPO_PATH}...")
        print(f"[{self.name}] Modelo configurado: {self.valves.MODEL_NAME}")

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Union[str, Generator, Iterator]:

        if self.valves.GEMINI_API_KEY:
            os.environ["GEMINI_API_KEY"] = self.valves.GEMINI_API_KEY
        if self.valves.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = self.valves.OPENAI_API_KEY
        if self.valves.ANTHROPIC_API_KEY:
            os.environ["ANTHROPIC_API_KEY"] = self.valves.ANTHROPIC_API_KEY

        model = self.valves.MODEL_NAME
        ultimo = messages[-1]['content']
        print(f"[{self.name}] Nueva consulta con modelo '{model}': {ultimo[:100]}...")

        try:
            respuesta = asyncio.run(ejecutar_pipeline_legal(messages, model))
            return respuesta
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(ejecutar_pipeline_legal(messages, model))
            finally:
                loop.close()
        except Exception as e:
            return f"Hubo un error al procesar la consulta legal: {str(e)}"