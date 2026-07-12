"""Taxonomia fija de la Biblioteca Inteligente de Marketing (FASE 2.3).

No hay tabla de carpetas en la base de datos: la estructura es una constante
Python que el panel admin usa para poblar los selectores de categoria/
subcategoria y para renderizar el arbol de navegacion, incluso para ramas
que todavia no tienen ningun LibraryAsset cargado.
"""

GENERIC_LIBRARY_FOLDERS: dict[str, list[str] | dict[str, list[str]]] = {
    # Marca: incluye Colores/Tipografías (estaban listadas sueltas en el pedido
    # original de Recursos Globales, pero son parte de la identidad de marca).
    "Marca": ["Logos", "Manual de identidad", "Colores", "Tipografías"],
    "Imágenes": [],
    "Videos": [],
    "Música": [],
    # Distinto de "Marca > Logos" (el logo propio de ESE cliente): logos
    # genéricos/reutilizables sin marca específica, tipicamente Recursos
    # Globales.
    "Logos genéricos": [],
    "Prompts": [],
    "Plantillas": [],
    "Recursos IA": [],
    "Redes Sociales": {
        "Instagram": ["Publicaciones", "Reels", "Historias", "Campañas"],
        "Facebook": ["Publicaciones", "Campañas"],
        "YouTube": ["Videos", "Shorts"],
        "LinkedIn": ["Publicaciones", "Campañas"],
    },
    "Campañas": ["Ideas de campañas"],
    "Calendarios editoriales": [],
    "Artículos": [],
    "Emails": [],
    "Landing Pages": [],
    "Documentación": [],
    "Contenido reutilizable": [],
}

# Extra especifico de eAlumina, no incluido por defecto para clientes nuevos
# (Terra Araras, Frecuencia Mahatma, etc. arrancan solo con GENERIC_LIBRARY_FOLDERS).
EALUMINA_EXTRA_FOLDERS: list[str] = ["Recursos terapéuticos"]


def folder_tree_for_client(extra_categories: list[str] | None = None) -> dict:
    """Arbol de carpetas para un cliente: genericas + extras propias del cliente
    (guardadas en Client.config['library_extra_categories'])."""
    tree = dict(GENERIC_LIBRARY_FOLDERS)
    for extra in extra_categories or []:
        tree.setdefault(extra, [])
    return tree
