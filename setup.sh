#!/bin/bash
set -e

echo "================================================="
echo "   INSTALADOR: ASISTENTE LEGALIZE (OPEN WEBUI)   "
echo "               Potenciado por UV ⚡               "
echo "================================================="

# 1. Detectar Sistema Operativo e instalar Ripgrep (rg) y curl
OS="$(uname -s)"
echo "[1/6] Detectando SO: $OS"
if [ "$OS" = "Linux" ]; then
    echo "Instalando ripgrep y dependencias base via APT..."
    sudo apt-get update && sudo apt-get install -y ripgrep curl
elif [ "$OS" = "Darwin" ]; then
    echo "Instalando ripgrep via Homebrew..."
    if ! command -v brew &> /dev/null; then
        echo "Error: Homebrew no está instalado. Instálalo primero."
        exit 1
    fi
    brew install ripgrep curl
fi

# 1.5. Instalar 'uv' si no está instalado
if ! command -v uv &> /dev/null; then
    echo "[+] Instalando uv (Astral)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Añadimos uv al PATH temporalmente para que el script pueda seguir usándolo
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[+] uv ya está instalado."
fi

# 2. Clonar servidor Open WebUI Pipelines
echo "[2/6] Preparando servidor de Pipelines..."
if [ ! -d "pipelines" ]; then
    git clone https://github.com/open-webui/pipelines.git
fi

# 3. Clonar repositorio de leyes dentro de pipelines
echo "[3/6] Clonando repositorio de leyes españolas (legalize-es)..."
if [ ! -d "pipelines/pipelines/legalize-es" ]; then
    git clone https://github.com/legalize-dev/legalize-es.git pipelines/pipelines/legalize-es
else
    echo "Repositorio legalize-es ya existe. Actualizando..."
    cd pipelines/pipelines/legalize-es && git pull && cd ../../../
fi

# 4. Copiar nuestro Pipeline y configuración
echo "[4/6] Configurando tu Agente y Dependencias..."
cp pipeline_legalize.py pipelines/pipelines/
# Copiamos el toml a la carpeta pipelines para instalarlo desde allí
cp requirements-legalize.txt pipelines/

# 5. Entorno Virtual y Dependencias con UV ⚡
echo "[5/6] Creando entorno virtual e instalando librerías con UV..."
cd pipelines
uv venv
source .venv/bin/activate

# uv es tan listo que puede leer requirements.txt clásicos y requirements-legalize.txt a la vez
echo "Instalando dependencias de Open WebUI Pipelines..."
uv pip install -r requirements.txt

echo "Instalando dependencias de tu Asistente Legal..."
uv pip install -r requirements-legalize.txt
cd ..

# 6. Archivo .env
echo "[6/6] Configurando variables de entorno..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "¡Atención! Hemos creado un archivo .env. Por favor, edítalo e introduce tu GEMINI_API_KEY."
fi

echo "================================================="
echo " ¡INSTALACIÓN COMPLETADA CON ÉXITO! 🚀           "
echo " Lee el README.md para saber cómo arrancarlo.    "
echo "================================================="