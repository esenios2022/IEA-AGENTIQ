#!/usr/bin/env python3
"""
setup_config.py - Configurador interactivo para AgentiQ TVD

Detecta modelos disponibles y permite al usuario configurar sus APIs
"""

import json
import os
import sys
import requests
from pathlib import Path

def detectar_ollama_modelos():
    """Detectar modelos disponibles en Ollama"""
    try:
        print("\n🔍 Buscando Ollama en http://localhost:11434...")
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.status_code == 200:
            data = response.json()
            modelos = [m['name'] for m in data.get('models', [])]
            if modelos:
                print(f"✅ Ollama encontrado. Modelos disponibles:")
                for i, modelo in enumerate(modelos, 1):
                    print(f"   {i}. {modelo}")
                return modelos
            else:
                print("⚠️ Ollama está corriendo pero sin modelos instalados.")
                print("   Ejecuta: ollama pull mistral (u otro modelo)")
                return []
        else:
            print("❌ Ollama no responde en http://localhost:11434")
            return []
    except requests.exceptions.ConnectionError:
        print("❌ Ollama NO está corriendo.")
        print("   Inicia Ollama con: ollama serve")
        return []
    except Exception as e:
        print(f"❌ Error conectando a Ollama: {e}")
        return []

def configurar_modelo():
    """Configurar qué modelo usar"""
    print("\n" + "="*60)
    print("SELECCIONAR MODELO DE IA")
    print("="*60)

    opciones = {
        '1': ('ollama', 'Ollama (Local)'),
        '2': ('openai', 'OpenAI (ChatGPT)'),
        '3': ('claude', 'Claude (Anthropic)'),
        '4': ('gemini', 'Google Gemini'),
        '5': ('grok', 'Grok (xAI)'),
        '6': ('local', 'Generación Local (sin API)'),
    }

    for key, (_, desc) in opciones.items():
        print(f"{key}. {desc}")

    while True:
        eleccion = input("\nElige una opción (1-6): ").strip()
        if eleccion in opciones:
            return opciones[eleccion][0]
        print("❌ Opción inválida")

def obtener_api_key(proveedor):
    """Obtener API key del usuario"""
    if proveedor == 'ollama':
        return None  # Ollama no necesita API key

    if proveedor == 'openai':
        print("\n📝 Necesitas una API key de OpenAI")
        print("   Obtén una en: https://platform.openai.com/api-keys")
        return input("Pega tu API key de OpenAI (o presiona Enter para saltear): ").strip() or None

    elif proveedor == 'claude':
        print("\n📝 Necesitas una API key de Anthropic (Claude)")
        print("   Obtén una en: https://console.anthropic.com/")
        return input("Pega tu API key de Anthropic (o presiona Enter para saltear): ").strip() or None

    elif proveedor == 'gemini':
        print("\n📝 Necesitas una API key de Google Gemini")
        print("   Obtén una en: https://makersuite.google.com/app/apikey")
        return input("Pega tu API key de Gemini (o presiona Enter para saltear): ").strip() or None

    elif proveedor == 'grok':
        print("\n📝 Necesitas una API key de Grok (xAI)")
        print("   Obtén una en: https://console.groq.com/keys")
        return input("Pega tu API key de Grok (o presiona Enter para saltear): ").strip() or None

    return None

def crear_config(modelo, api_key, ollama_model):
    """Crear archivo config.json"""
    config = {
        "modelo": modelo,
        "idioma": "es",
        "debug": False,
    }

    if modelo == "ollama":
        config["ollama_url"] = "http://localhost:11434"
        config["ollama_model"] = ollama_model or "mistral"
    elif modelo == "openai":
        config["openai_model"] = "gpt-3.5-turbo"
        if api_key:
            config["api_key"] = api_key
    elif modelo == "claude":
        config["claude_model"] = "claude-3-sonnet-20240229"
        if api_key:
            config["api_key"] = api_key
    elif modelo == "gemini":
        config["gemini_model"] = "gemini-pro"
        if api_key:
            config["api_key"] = api_key
    elif modelo == "grok":
        config["grok_model"] = "mixtral-8x7b-32768"
        if api_key:
            config["api_key"] = api_key

    return config

def main():
    print("\n" + "="*60)
    print("🚀 CONFIGURADOR DE AGENTIQ TVD")
    print("="*60)

    # Detectar Ollama
    modelos_ollama = detectar_ollama_modelos()

    # Configurar modelo
    modelo = configurar_modelo()

    # Obtener API key si es necesario
    api_key = obtener_api_key(modelo)

    # Seleccionar modelo Ollama si es la opción
    ollama_model = None
    if modelo == "ollama" and modelos_ollama:
        print("\n¿Cuál modelo de Ollama deseas usar?")
        for i, m in enumerate(modelos_ollama, 1):
            print(f"{i}. {m}")
        try:
            opcion = int(input("Selecciona (número): ").strip()) - 1
            if 0 <= opcion < len(modelos_ollama):
                ollama_model = modelos_ollama[opcion]
        except ValueError:
            pass

    # Crear configuración
    config = crear_config(modelo, api_key, ollama_model)

    # Guardar a config.json
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("\n✅ Configuración guardada en config.json")
    print(f"   Modelo: {modelo}")
    print(f"   Idioma: {config.get('idioma')}")

    if modelo == "ollama":
        print(f"   Ollama URL: {config.get('ollama_url')}")
        print(f"   Ollama Model: {config.get('ollama_model')}")

    print("\n✅ ¡Listo para usar AgentiQ TVD!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Configuración cancelada.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
