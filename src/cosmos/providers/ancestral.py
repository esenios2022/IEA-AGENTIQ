"""
FASE 3.0 (Departamento Cosmos) — Tradiciones Ancestrales. Arquitectura
lista para sumar módulos futuros (chamanismo indígena, u otras
tradiciones) sin tocar el resto del sistema — pedido explícito del
usuario. Sin contenido real todavía: el registro empieza vacío a
propósito, y src/strategic_intelligence.py no invoca a este especialista
si un cliente no tiene ningún módulo configurado (nada que fabricar).

Para sumar una tradición real en el futuro: escribir una clase que
implemente `AncestralModuleProvider` y agregarla a `MODULE_REGISTRY` con
una clave — esa clave es lo que un cliente activa en
`Client.config["ancestral_modules"]`. Cero cambios en el agente, el
orquestador ni el resto del departamento.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AncestralModuleContent:
    module_key: str
    label: str
    summary: str


class AncestralModuleProvider(ABC):
    @abstractmethod
    def get_content(self) -> AncestralModuleContent: ...


# Vacío a propósito — ver docstring del módulo.
MODULE_REGISTRY: dict[str, AncestralModuleProvider] = {}


def get_active_modules(module_keys: list[str]) -> list[AncestralModuleContent]:
    """Solo devuelve contenido para claves realmente registradas — una clave
    pedida por un cliente que todavía no tiene módulo real se ignora en
    silencio (no se fabrica contenido), no lanza error."""
    return [MODULE_REGISTRY[key].get_content() for key in module_keys if key in MODULE_REGISTRY]
