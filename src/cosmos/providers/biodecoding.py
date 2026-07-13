"""
FASE 3.0 (Departamento Cosmos) — Biodescodificación: base documental
curada de categorías generales del enfoque (asociaciones simbólicas
sistema corporal ↔ tema emocional, tal como las plantea esta corriente),
NUNCA un diagnóstico ni una afirmación médica sobre una persona real —
mismo criterio que ya aplicamos en el Manual de Identidad de eAlumina
("perspectivas terapéuticas o simbólicas, no diagnósticos ni hechos
médicos"). A diferencia de Astronomía/Maya/Dreamspell, esto no tiene
dimensión calendárica — es una tabla de referencia, no un cálculo por
fecha.

Interfaz `BiodecodingKnowledgeProvider` desacoplada, mismo patrón que el
resto — una base documental distinta (otra corriente, otra fuente
curada) sería otra clase, sin tocar el especialista ni el orquestador.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

DISCLAIMER = (
    "Estas asociaciones son la perspectiva simbólica de este enfoque específico, "
    "no un diagnóstico médico ni una afirmación científica validada."
)


@dataclass
class BiodecodingCategory:
    body_system: str
    symbolic_theme: str


GENERAL_CATEGORIES = [
    BiodecodingCategory("Sistema digestivo", "Aquello que cuesta 'digerir' — una situación, una noticia, un cambio no asimilado."),
    BiodecodingCategory("Sistema respiratorio", "El espacio propio — miedo a ocupar lugar, o necesidad de más autonomía para respirar."),
    BiodecodingCategory("Piel", "Contacto y límites — la frontera entre uno mismo y el entorno, separación o falta de contacto."),
    BiodecodingCategory("Sistema musculoesquelético", "Sostén y estructura — la sensación de tener que sostener demasiado, o de perder apoyo."),
    BiodecodingCategory("Sistema cardiovascular", "Vínculos afectivos — lo que se da y se recibe en una relación importante."),
]


class BiodecodingKnowledgeProvider(ABC):
    @abstractmethod
    def get_categories(self) -> list[BiodecodingCategory]: ...

    @abstractmethod
    def get_disclaimer(self) -> str: ...


class CuratedBiodecodingProvider(BiodecodingKnowledgeProvider):
    def get_categories(self) -> list[BiodecodingCategory]:
        return list(GENERAL_CATEGORIES)

    def get_disclaimer(self) -> str:
        return DISCLAIMER
