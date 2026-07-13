"""
FASE 3.0 (Departamento Cosmos) — Dreamspell / calendario de 13 Lunas,
especialista SEPARADO del Calendario Maya clásico a propósito (ver
src/cosmos/providers/maya.py). Sistema moderno creado por José Argüelles
en 1987, NO tradición maya ancestral — cada salida de este provider debe
citarse como tal, nunca como "calendario maya".

Época de referencia verificada (2026-07-13, búsqueda real, no asumida):
26 de julio de 1987 = Kin 1 (Dragón Rojo Magnético). El propio sistema
Dreamspell no cuenta el 29 de febrero en su ciclo ("se cuenta como 0.0
Hunab Ku") — se ajusta explícitamente acá, no se ignora.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

DREAMSPELL_EPOCH = date(1987, 7, 26)  # Kin 1

SOLAR_SEALS = [
    "Dragón", "Viento", "Noche", "Semilla", "Serpiente", "Enlazador de Mundos", "Mano", "Estrella",
    "Luna", "Perro", "Mono", "Humano", "Caminante del Cielo", "Mago", "Águila", "Guerrero",
    "Tierra", "Espejo", "Tormenta", "Sol",
]

SEAL_COLORS = ["Rojo", "Blanco", "Azul", "Amarillo"]  # se repite cada 4 sellos, ciclo de color Dreamspell

TONES = [
    "Magnético", "Lunar", "Eléctrico", "Autoexistente", "Entonado", "Rítmico", "Resonante",
    "Galáctico", "Solar", "Planetario", "Espectral", "Cristal", "Cósmico",
]


def _leap_days_between(start: date, end: date) -> int:
    """29 de febrero no se cuenta en el ciclo Dreamspell — se resta explícitamente."""
    sign = 1 if end >= start else -1
    lo, hi = (start, end) if end >= start else (end, start)
    count = sum(1 for year in range(lo.year, hi.year + 1) if _is_leap(year) and lo <= date(year, 2, 29) <= hi)
    return sign * count


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


@dataclass
class KinDate:
    kin_number: int  # 1-260
    tone: str
    seal: str
    seal_color: str

    def __str__(self) -> str:
        return f"Kin {self.kin_number}: {self.tone} {self.seal} {self.seal_color}"


@dataclass
class WavespellInfo:
    number: int  # 1-20
    seed_seal: str


@dataclass
class DreamspellSnapshot:
    gregorian_date: date
    kin: KinDate
    wavespell: WavespellInfo
    is_day_out_of_time: bool  # 25 de julio, fuera del conteo de 365/260


class DreamspellProvider(ABC):
    @abstractmethod
    def get_snapshot(self, target_date: date) -> DreamspellSnapshot: ...


class ClassicDreamspellProvider(DreamspellProvider):
    def get_snapshot(self, target_date: date) -> DreamspellSnapshot:
        raw_days = (target_date - DREAMSPELL_EPOCH).days
        adjusted_days = raw_days - _leap_days_between(DREAMSPELL_EPOCH, target_date)

        kin_number = (adjusted_days % 260) + 1
        seal_index = (kin_number - 1) % 20
        tone_index = (kin_number - 1) % 13

        wavespell_index = (kin_number - 1) // 13
        wavespell_seed_seal = SOLAR_SEALS[(wavespell_index * 13) % 20]

        kin = KinDate(
            kin_number=kin_number,
            tone=TONES[tone_index],
            seal=SOLAR_SEALS[seal_index],
            seal_color=SEAL_COLORS[seal_index % 4],
        )
        wavespell = WavespellInfo(number=wavespell_index + 1, seed_seal=wavespell_seed_seal)
        is_day_out_of_time = target_date.month == 7 and target_date.day == 25

        return DreamspellSnapshot(
            gregorian_date=target_date, kin=kin, wavespell=wavespell, is_day_out_of_time=is_day_out_of_time,
        )
