# Estructura base de los agentes — EA Lumina / AgentiQ

Principio: **todos los agentes parten de la misma base** (mismas capacidades y mismas herramientas).
Cada agente = **Base común + especialización**. Así son consistentes, fáciles de mantener y se configuran rápido para cualquier cliente.

---

## 1. Capacidades comunes (las tiene TODO agente)

| Capacidad | Qué hace |
|---|---|
| Bilingüe PT-BR + ES | Trabaja en portugués y español según el mercado del cliente |
| Registro de pasos legible | Escribe cada acción en lenguaje humano → alimenta el workspace |
| Compuerta de aprobación | Espera el "sí/no" del cliente antes de acciones sensibles (envíos, publicaciones) |
| Medición de costo | Cuenta tokens por tarea → alimenta el saldo y los límites de gasto |
| Memoria / base de conocimiento | Accede al contexto y datos del cliente |
| Manejo de errores | Reintenta, avisa y no se cuelga; registra el fallo |
| Límite de gasto | Respeta el tope diario configurado por el cliente |

## 2. Herramientas comunes (caja de herramientas compartida)

| Herramienta | Uso |
|---|---|
| Búsqueda web | Investigar cualquier tema o empresa |
| Extraer texto de URL | Leer páginas, perfiles, artículos |
| Email (Gmail) | Enviar y leer correos |
| WhatsApp (API oficial) | Mensajería y difusión conforme a normas |
| LinkedIn | Buscar, extraer y contactar |
| Enriquecedor de leads | Completar datos de contactos (tipo Apollo) |
| Base de datos / CRM | Guardar y consultar contactos, tareas, resultados |
| Archivos / documentos | Leer y escribir (listas, reportes) |
| Agenda / programador | Agendar envíos, seguimientos y publicaciones |
| Generación de contenido | Producir texto e imágenes |

## 3. Especialización (lo que distingue a cada agente)

Sobre la base, cada agente suma:
- **Prompt específico** (su tarea y criterio, original y en el idioma/voz del cliente).
- **Herramientas extra** puntuales si su función lo requiere (ej. cortar video).
- **Permisos** según qué puede hacer solo y qué necesita aprobación.

> Regla previa siempre vigente: antes de crear agentes, **preguntar para qué cliente/negocio son**. La base es la misma; la voz, el idioma y las integraciones se ajustan a ese cliente.

---

## Referencia — empresas en la web de Relevance AI
Prueba social de Relevance (no socios nuestros), útil como referencia de rubros donde estos agentes rinden:
- **Prensa:** Fortune, Forbes, TechCrunch, The Information.
- **Clientes/usuarios:** Canva, Rakuten, Databricks, Freshworks, Confluent, AVEVA, Autodesk, Activision Blizzard, Lightspeed, Qualified, ThoughtSpot, Employment Hero, Zembl, Stride.
