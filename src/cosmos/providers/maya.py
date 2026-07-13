"""
FASE 3.0 (Departamento Cosmos) — Tzolkin/Haab clásicos, tradición maya
real y verificable (NO el Dreamspell moderno — ver src/cosmos/providers/
dreamspell.py, especialista separado a propósito).

Algoritmo: correlación GMT (Goodman-Martínez-Thompson) = 584283, el mismo
valor que usa mayan.org/calendar/converter (confirmado 2026-07-13, fuente
independiente, no asumido) — ancla la fecha de creación 0.0.0.0.0 = 4 Ajaw
8 Kumk'u = 11 de agosto de 3114 a.C. (proléptico gregoriano). Verificado
en tests contra ese mismo punto de referencia (el único 100% consensuado
en la literatura maya) y contra una fecha moderna publicada.

Interfaz `MayaCalendarProvider` desacoplada de la implementación, mismo
patrón que astronomy.py — otra correlación (584285, 584286, discutidas
por algunos investigadores) sería otra clase, sin tocar el resto.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

GMT_CORRELATION = 584283

TZOLKIN_DAY_NAMES = [
    "Imix", "Ik'", "Ak'b'al", "K'an", "Chikchan", "Kimi", "Manik'", "Lamat", "Muluk", "Ok",
    "Chuwen", "Eb'", "B'en", "Ix", "Men", "K'ib'", "Kab'an", "Etz'nab'", "Kawak", "Ajaw",
]

HAAB_MONTH_NAMES = [
    "Pop", "Wo'", "Sip", "Sotz'", "Sek", "Xul", "Yaxk'in", "Mol", "Ch'en", "Yax",
    "Sac", "Keh", "Mak", "K'ank'in", "Muwan", "Pax", "K'ayab", "Kumk'u", "Wayeb'",
]


def gregorian_to_jdn(year: int, month: int, day: int) -> int:
    """Fórmula estándar de Fliegel & Van Flandern (Julian Day Number)."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


@dataclass
class TzolkinDate:
    number: int  # 1-13
    day_name: str  # uno de TZOLKIN_DAY_NAMES

    def __str__(self) -> str:
        return f"{self.number} {self.day_name}"


@dataclass
class HaabDate:
    day: int  # 0-19
    month_name: str  # uno de HAAB_MONTH_NAMES

    def __str__(self) -> str:
        return f"{self.day} {self.month_name}"


@dataclass
class MayaCalendarSnapshot:
    gregorian_date: date
    tzolkin: TzolkinDate
    haab: HaabDate
    long_count_days: int  # días desde la fecha de creación (0.0.0.0.0)


class MayaCalendarProvider(ABC):
    @abstractmethod
    def get_snapshot(self, target_date: date) -> MayaCalendarSnapshot: ...


class GMTCorrelationProvider(MayaCalendarProvider):
    def get_snapshot(self, target_date: date) -> MayaCalendarSnapshot:
        jdn = gregorian_to_jdn(target_date.year, target_date.month, target_date.day)
        long_count_days = jdn - GMT_CORRELATION

        tzolkin_number = ((long_count_days + 3) % 13) + 1
        tzolkin_name = TZOLKIN_DAY_NAMES[(long_count_days + 19) % 20]

        haab_position = (long_count_days + 348) % 365
        haab_month = HAAB_MONTH_NAMES[haab_position // 20]
        haab_day = haab_position % 20

        return MayaCalendarSnapshot(
            gregorian_date=target_date,
            tzolkin=TzolkinDate(tzolkin_number, tzolkin_name),
            haab=HaabDate(haab_day, haab_month),
            long_count_days=long_count_days,
        )
