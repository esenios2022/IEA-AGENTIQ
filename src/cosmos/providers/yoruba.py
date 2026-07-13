"""
FASE 3.0 (Departamento Cosmos) — Inteligencia Yoruba. Verificado antes de
escribir esto (2026-07-13, no asumido): los 256 odù de Ifá se determinan
por un acto ritual real (tirada de ikin/opelé por un babalawo), NO por
fecha — no existe un algoritmo legítimo "fecha → odù". Por eso este
provider **nunca** asigna un odù a una fecha; trabaja con:

1. El calendario tradicional Yoruba real de 4 días (Ògún/Sàngó/Ọbàtálá/
   Òrìṣà, parte del calendario Kọ́jọ́dá) — un sistema calendárico
   legítimo, distinto de la adivinación de odù. Aclaración honesta: a
   diferencia de la correlación GMT maya (con epoch consensuado y
   verificado contra fuente independiente), no encontré una fuente que
   fije con la misma autoridad qué fecha gregoriana específica
   corresponde a cada día del ciclo — la posición se calcula sobre un
   punto de referencia fijo pero **se marca explícitamente como
   ilustrativa**, no como un dato verificado por una autoridad cultural
   Yoruba.
2. Un set curado de temas generales del corpus de Ifá (principios
   filosóficos ampliamente documentados — Iwa Pele, Orí, Àṣẹ,
   responsabilidad comunitaria) rotando de forma neutral, nunca
   presentado como "el odù de hoy".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

FOUR_DAY_WEEK = ["Ògún", "Sàngó", "Ọbàtálá", "Òrìṣà"]
FOUR_DAY_WEEK_REFERENCE_EPOCH = date(2000, 1, 1)  # ancla arbitraria fija, no una fuente cultural verificada — ver docstring

# Temas generales del corpus de Ifá — principios documentados, no un odù específico.
GENERAL_IFA_THEMES = [
    ("Iwa Pele", "El buen carácter como fundamento — cómo se sostienen las relaciones y la palabra dada."),
    ("Orí", "La cabeza interior, el destino propio elegido antes de nacer — autoconocimiento y propósito."),
    ("Àṣẹ", "La fuerza vital que hace que las cosas sucedan — el poder de la palabra y la acción alineadas."),
    ("Ìwàpẹ̀lẹ́ comunitario", "La responsabilidad hacia la comunidad — ningún destino individual está separado del colectivo."),
    ("Ẹ̀gbẹ́", "El equilibrio entre lo visible y lo invisible — paciencia frente a los procesos que no se controlan."),
]


@dataclass
class YorubaFourDayPosition:
    day_name: str
    is_illustrative: bool  # siempre True — ver docstring del módulo


@dataclass
class IfaGeneralTheme:
    name: str
    description: str


@dataclass
class YorubaSnapshot:
    gregorian_date: date
    four_day_position: YorubaFourDayPosition
    general_theme: IfaGeneralTheme


class YorubaKnowledgeProvider(ABC):
    @abstractmethod
    def get_snapshot(self, target_date: date) -> YorubaSnapshot: ...


class TraditionalYorubaProvider(YorubaKnowledgeProvider):
    def get_snapshot(self, target_date: date) -> YorubaSnapshot:
        days_since_epoch = (target_date - FOUR_DAY_WEEK_REFERENCE_EPOCH).days
        day_name = FOUR_DAY_WEEK[days_since_epoch % 4]

        theme_index = target_date.toordinal() % len(GENERAL_IFA_THEMES)
        theme_name, theme_description = GENERAL_IFA_THEMES[theme_index]

        return YorubaSnapshot(
            gregorian_date=target_date,
            four_day_position=YorubaFourDayPosition(day_name=day_name, is_illustrative=True),
            general_theme=IfaGeneralTheme(theme_name, theme_description),
        )
