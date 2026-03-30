# Legalize AI Assistant

Un Agente de IA para interactuar con la legislación española (BOE) en lenguaje natural, alimentado por el repositorio [legalize-es](https://github.com/legalize-dev/legalize-es).

## Requisitos previos

- **Docker** (para correr Open WebUI).
- **Tu API Key de Google Gemini** (consíguela en [Google AI Studio](https://aistudio.google.com/app/apikey)).

## Instalación (Mac & WSL)

1. Abre tu terminal y ejecuta el instalador automático:

```bash
chmod +x setup.sh
./setup.sh
```

---

## Configuración inicial



1. Abre el archivo `.env` que se acaba de crear y pega tu `GEMINI_API_KEY`.

---

## Cómo arrancar el sistema

Necesitas correr dos procesos simultáneamente en dos pestañas diferentes de tu terminal: el **Servidor de Agentes (Pipelines)** y el **Frontend (Open WebUI)**.

### 1. Arrancar el Servidor de Agentes (Pipelines)

En la primera pestaña de tu terminal, levanta el servidor de Python que aloja tus agentes:

```bash
cd pipelines
source .venv/bin/activate
export GEMINI_API_KEY=$(cat ../.env | grep GEMINI_API_KEY | cut -d '=' -f2 | tr -d '"')
./start.sh
```

> **Nota:** El servidor de agentes indicará que se queda escuchando en el puerto `9099`. Déjalo corriendo.

### 2. Arrancar Open WebUI (Docker)

Abre una **nueva pestaña** en tu terminal (sin cerrar la anterior) y levanta la interfaz gráfica con Docker. Usamos `host.docker.internal` para que el contenedor pueda comunicarse con el puerto `9099` de tu máquina local (tanto en WSL como en Mac):

```bash
docker run -d -p 3000:8080 -e PIPELINES_URLS=http://host.docker.internal:9099 \
-v open-webui:/app/backend/data --name open-webui ghcr.io/open-webui/open-webui:main
```

Si no pudiera encontrarse host.docker.internal entonces utilizar el siguiente comando para averiguar la IP real de tu WSL.

```bash
ip addr show eth0 | grep "inet " | awk '{print $2}' | cut -d/ -f1
```
Seguidamente debemos borrar el contenedor de openwebui y volverlo a crear con la IP que nos devuelva el comando anterior:

```bash
docker rm -f open-webui

docker run -d -p 3000:8080 \
  -e PIPELINES_URLS=http://<TU_IP_WSL>:9099 \
  -v open-webui:/app/backend/data \
  --name open-webui \
  ghcr.io/open-webui/open-webui:main
```

Para ver los logs utilizar el siguiente comando:

```bash
docker logs -f open-webui
```
---

## Uso y configuración final

1. Abre tu navegador web y dirígete a: [http://localhost:3000](http://localhost:3000)
2. Crea una cuenta (el primer usuario que se registra se convierte automáticamente en administrador local).
3. En la esquina superior izquierda, haz clic en el selector de modelos.
4. Selecciona el modelo llamado **"Asistente Legalize (BOE)"**.
5. *(Opcional)* Si la API Key no se cargó automáticamente, puedes ir al icono de tu perfil → **Ajustes** → **Workspace** → **Models**, buscar el "Asistente Legalize" y en el apartado **Valves** pegar tu `GEMINI_API_KEY`.

### Solución de problemas: el pipeline no aparece en Open WebUI
 
Si tras arrancar el contenedor el modelo no aparece en el selector, configura la conexión manualmente:
 
1. Ve a tu perfil → **Admin Panel** → **Settings** → **Connections**
2. En la sección de conexiones OpenAI/Pipelines, añade:
   - **URL:** `http://<TU_IP_WSL>:9099`
   - **API Key:** `0p3n-w3bu!` (el campo no puede estar vacío, pero el servidor no valida el valor)
3. Guarda y recarga la página.
 
> **Nota:** Los errores `Cannot connect to host.docker.internal:11434` son esperados si no tienes Ollama instalado. No afectan al funcionamiento del pipeline.
 

---

## Ejemplos de uso

Prueba a escribir en el chat consultas como:

- *"¿Qué dice la ley de enjuiciamiento civil sobre los desahucios?"*
- *"¿Cuántos días tengo para recurrir un despido disciplinario y en qué ley aparece?"*
- *"¿Cuáles son los requisitos para el cambio de sexo registral?"*

El sistema ejecutará consultas mediante **Ripgrep** en tu equipo local, leerá los artículos exactos del repositorio de `legalize-es`, formulará una respuesta limpia de contexto y te devolverá las referencias con **enlaces directos a la web oficial del BOE**.