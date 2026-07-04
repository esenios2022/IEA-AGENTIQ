# 🚀 INSTALACIÓN Y CONFIGURACIÓN — AgentiQ TVD

## 📋 Requisitos Previos

- Python 3.8+
- Node.js 16+
- Rust y Cargo (para compilar Tauri)
- Git

## 🔧 PASO 1: Configurar el Agente

AgentiQ TVD soporta **múltiples APIs**. Elige una:

### Opción A: Ollama (Recomendado - Local, Gratuito)

1. **Descarga e instala Ollama:**
   ```bash
   # Windows: https://ollama.ai/download/windows
   # Mac: https://ollama.ai/download/macos
   # Linux: https://ollama.ai/download/linux
   ```

2. **Descargar un modelo:**
   ```bash
   ollama pull mistral          # Rápido, buena calidad
   ollama pull neural-chat      # Excelente para chat
   ollama pull llama2           # Muy bueno, más lento
   ollama pull dolphin-mixtral  # Muy poderoso
   ```

3. **Inicia Ollama:**
   ```bash
   ollama serve
   ```
   (Déjalo corriendo en segundo plano)

4. **Ejecuta el configurador:**
   ```bash
   python setup_config.py
   ```
   - Elige opción: **1 (Ollama)**
   - Selecciona el modelo que instalaste

### Opción B: OpenAI (ChatGPT)

1. **Obtén una API key:**
   - Ve a https://platform.openai.com/api-keys
   - Crea una nueva key

2. **Ejecuta el configurador:**
   ```bash
   python setup_config.py
   ```
   - Elige opción: **2 (OpenAI)**
   - Pega tu API key

### Opción C: Claude (Anthropic)

1. **Obtén una API key:**
   - Ve a https://console.anthropic.com/
   - Crea una nueva key

2. **Ejecuta el configurador:**
   ```bash
   python setup_config.py
   ```
   - Elige opción: **3 (Claude)**
   - Pega tu API key

### Opción D: Google Gemini

1. **Obtén una API key:**
   - Ve a https://makersuite.google.com/app/apikey
   - Genera una key gratuita

2. **Ejecuta el configurador:**
   ```bash
   python setup_config.py
   ```
   - Elige opción: **4 (Gemini)**
   - Pega tu API key

### Opción E: Grok (xAI)

1. **Obtén una API key:**
   - Ve a https://console.groq.com/keys
   - Crea una nueva key

2. **Ejecuta el configurador:**
   ```bash
   python setup_config.py
   ```
   - Elige opción: **5 (Grok)**
   - Pega tu API key

### Opción F: Generación Local (Sin API)

No necesita configuración. Solo genera respuestas locales simples.

---

## 📦 PASO 2: Instalar Dependencias

### Backend (Rust/Tauri)

```bash
cd AgentiQ\ TVD
cargo build
```

### Frontend (Python)

```bash
pip install requests anthropic groq google-generativeai openai
```

---

## ▶️ PASO 3: Ejecutar en Desarrollo

```bash
cargo tauri dev
```

O si ya compilaste:
```bash
./src-tauri/target/release/AgentiQ\ TVD.exe
```

---

## 🏗️ PASO 4: Compilar para Producción

```bash
cargo tauri build
```

El .exe compilado estará en:
```
src-tauri/target/release/AgentiQ\ TVD.exe
```

---

## 📝 Estructura de config.json

### Con Ollama:
```json
{
  "modelo": "ollama",
  "ollama_url": "http://localhost:11434",
  "ollama_model": "mistral",
  "idioma": "es",
  "debug": false
}
```

### Con OpenAI:
```json
{
  "modelo": "openai",
  "openai_model": "gpt-3.5-turbo",
  "api_key": "sk-...",
  "idioma": "es",
  "debug": false
}
```

### Con Claude:
```json
{
  "modelo": "claude",
  "claude_model": "claude-3-sonnet-20240229",
  "api_key": "sk-ant-...",
  "idioma": "es",
  "debug": false
}
```

### Con Gemini:
```json
{
  "modelo": "gemini",
  "gemini_model": "gemini-pro",
  "api_key": "AIza...",
  "idioma": "es",
  "debug": false
}
```

### Con Grok:
```json
{
  "modelo": "grok",
  "grok_model": "mixtral-8x7b-32768",
  "api_key": "gsk_...",
  "idioma": "es",
  "debug": false
}
```

### Generación Local:
```json
{
  "modelo": "local",
  "idioma": "es",
  "debug": false
}
```

---

## 🔄 Cambiar de Modelo Después

1. **Edita `config.json` directamente**, O
2. **Ejecuta nuevamente `python setup_config.py`**

---

## 💬 Cambiar Idioma

En la interfaz de AgentiQ TVD:
- Botón "Español" / "Português" en la esquina superior derecha
- Se guarda automáticamente en localStorage

---

## ⚠️ Troubleshooting

### Ollama no conecta
```bash
# Verifica que Ollama esté corriendo:
curl http://localhost:11434/api/tags

# Si no funciona, reinicia Ollama:
ollama serve
```

### API key rechazada
- OpenAI: https://platform.openai.com/account/billing/usage
- Claude: Verifica que tengas créditos en https://console.anthropic.com/
- Gemini: Usa una API key generada (no OAuth)
- Grok: Obtén una en https://console.groq.com/

### Python imports error
```bash
pip install --upgrade openai anthropic groq google-generativeai requests
```

### Tauri build error
```bash
# Windows: Instala Visual Studio Build Tools
# Mac: Instala Xcode Command Line Tools: xcode-select --install
# Linux: sudo apt install build-essential
```

---

## ✅ Verificar Configuración

```bash
python agentes_unificado.py --estado
```

Debería mostrar algo como:
```json
{
  "modelo": "ollama",
  "idioma": "es",
  "ollama_disponible": true,
  "ollama_url": "http://localhost:11434",
  "ollama_model": "mistral"
}
```

---

## 🎯 Listo!

AgentiQ TVD está configurado y listo para usar. Abre en el navegador o ejecuta el .exe compilado.

**¿Preguntas?** Revisa los logs en la consola.
