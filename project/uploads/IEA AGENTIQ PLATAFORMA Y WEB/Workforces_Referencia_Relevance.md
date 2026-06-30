# Workforces de referencia — Relevance AI
### Los mejores/más clonados, analizados por Fabián como referencia (jun 2026)

> Uso: estudiar cómo arman los workforces más exitosos para diseñar los nuestros. Las listas de tools son aproximadas (identificadas de la web). La base común propia está en `Estructura_Base_Agentes.md`; el catálogo y la plantilla en `Catalogo_Tools_Integraciones_Workforce.md`.

## Índice comparativo

| Workforce | Agentes | Tools | Integr. | Clones | Rating | Modelo |
|---|---|---|---|---|---|---|
| Multi-Platform Workforce | 16 | 27+ | 11+ | 1.834 | 3.6★ | Amplio / multi-servicio |
| GSuite Workforce | 7 | 16 | 7 | 632 | 3.5★ | Especializado / Google |
| AI Content Writing Team | 7 | 16 | 4 | 436 | 4.0★ | Contenido / social (premium $5.99) |
| Instant Lead List Generator | 3 | 1 | 1 | 425 | **4.7★** | Lead gen / pipeline minimalista |
| Tari-AI-ntino Video Generator | 2+ | varias+APIs | varias | 308 | — | Video publicitario IA / cadena |
| Competitor Spy | 4 (1 orquestador+3) | varias+APIs | Meta/Google/web | — | — | Inteligencia competitiva / orquestador |

**Aprendizaje clave:** existen dos modelos válidos — (a) **especializado y simple** (pocos agentes/tools, fácil de mantener, ideal para un cliente de un solo ecosistema) y (b) **amplio multi-plataforma** (muchos agentes/tools, más potente y complejo). Ambos incluyen un **agente Manager/orquestador** (patrón director). Elegir el modelo según el cliente.

---

## 1. Multi-Platform Workforce
Detalle completo en `Catalogo_Tools_Integraciones_Workforce.md`. Resumen: 16 agentes en 6 grupos (Google Suite, Plataformas, Contenido, CRM, Datos, Almacenamiento). Orquestador = **MRP Manager**. Integraciones destacadas: HubSpot, Salesforce, Webflow, Gamma, Apollo, Brandfetch, Zapier.

## 2. GSuite Workforce
- **Tipo:** especializado en Google Workspace · **Complejidad:** baja-media · **Mantenibilidad:** alta
- **Clones:** 632 · **Rating:** 3.5★ (4)
- **Tools (16):** Gmail, Google Chat, Drive, Forms, Photos, Maps, Search/Web, Docs, Sheets, Slides, Google Cloud, Analytics, OpenAI/ChatGPT, Gemini, Workspace monitor.
- **Integraciones (7):** Docs, Sheets, Drive, Gmail, Google Search, **Bing**, Drive/Cloud.
- **Agentes (7):**
  1. Gmail Assistant — todo en Gmail
  2. Google Sheets Assistant — Sheets + Drive
  3. Google Slides Assistant — Slides + Drive
  4. **GSuite Manager** — orquesta los agentes GSuite (MRP)
  5. Research Assistant — investiga/extrae de internet (Search + Bing)
  6. Google Docs Assistant — Docs + Drive
  7. Google Drive Assistant — gestión de archivos/carpetas/permisos
- **Caso de uso:** empresas que viven en Google Workspace; automatización documental + investigación web.

---

## 3. AI Content Writing Team
- **Creador:** Altari (comunidad, NO Relevance) · **Premium $5.99** · **Clones:** 436 · **Rating:** 4.0★ (2)
- **Categorías:** Fun, Marketing, Content creation · **Modelo:** equipo de contenido especializado
- **Tools (16):** Google Search, web/browser, imágenes, LinkedIn, X/Twitter, Instagram, TikTok, YouTube, OpenAI/GPT-4, mensajería, Notion, markdown/documentos, diseño gráfico vectorial.
- **Integraciones (4):** Google Docs, settings, Bing, YouTube.
- **Agentes (nombres de filósofos, por rol):**
  1. **Socrates** — cuestiona y desarrolla ideas (ideación/brainstorming). Tools: Search, OpenAI.
  2. **Cicero** — transforma el contenido en algo viral. Tools: redes sociales, OpenAI.
  3. **Ovid** — adapta el texto a formatos LinkedIn, X y newsletter (repurposing multiplataforma). Tools: LinkedIn, X, Google Docs.
  4. **Ptolemy** — crea el prompt de imagen y genera el arte. Tools: OpenAI/DALL-E.
  5. **Plutarch** — escribe guiones de video largo y corto. Tools: YouTube, TikTok, OpenAI.
  6. **Xenophon** — toma TODAS las salidas y las guarda permanentemente en un Google Doc (consolidación/archivo). Tools: Google Docs, Drive.
  *(El doc indica 7 agentes; el 7º — probablemente el orquestador — quedó sin listar.)*
- **Patrón clave:** equipo de roles que se pasan el trabajo en cadena (idea → viralizar → adaptar por canal → imagen → video → consolidar). Encaja directo con nuestros agentes de contenido (7 Fragmentador, 8 Copy+hashtags, 9 Publicador omnicanal) y aporta el patrón del **agente consolidador** (Xenophon) que junta todo en un solo documento final.

---

## 4. Instant Lead List Generator
- **Creador:** Nino (comunidad, NO Relevance) · **Clones:** 425 · **Rating:** 4.7★ (3) — **el mejor puntuado hasta ahora**
- **Categorías:** Research, Marketing, Sales · **Origen:** hackathon Liam Ottley × AAA Accelerator
- **Enfoque:** "de idea de nicho a JSON" — encuentra, limpia y formatea leads de venta.
- **Tools (1):** solo Google Search. **Integraciones (1):** Google.
- **Agentes (3) — arquitectura de pipeline (cadena secuencial):**
  1. **Data Researcher** — búsqueda web inteligente según el pedido del usuario → datos brutos de empresas.
  2. **Data Synthesizer** — limpia y estandariza los datos brutos a un formato de texto predecible.
  3. **Structured Extractor** — parsea ese texto y lo convierte en un array JSON final, listo para otras apps.
- **Patrón clave (¡el más valioso!):** **pipeline minimalista** crudo → limpio → estructurado (JSON). El mejor puntuado del lote logra el resultado con **1 herramienta y 3 agentes** — la calidad viene de la *arquitectura*, no de acumular tools. La salida JSON permite handoff limpio a CRM/otras apps. Modelo directo para nuestros agentes 1 (Prospector), 3 (Calificador) y 5 (Limpiador de listas).

---

## 5. Tari-AI-ntino Video Generator
- **Creador:** "Fine tuned and furious" (comunidad) · **Clones:** 308 · **Categoría:** Content creation
- **Objetivo:** crear anuncios de video de empresas a partir de investigación profunda — varios videos IA con audio, compilados en un solo MP4 (1280×720).
- **Agentes (cadena de 2):**
  1. **Video Content Creator** — investiga (Google Search + extraer web), arma el script social, genera prompts de video (Kling AI: imagen→video) y audio (Text to Audio). Modelo: uno potente (Claude Sonnet 4) por la parte creativa.
  2. **Splice (Video Stitcher)** — recibe URLs de clips + pista de audio, arma la timeline y llama a la **Shotstack render API** (POST para renderizar, GET para monitorear) → MP4 final. Modelo: uno económico (Haiku) por ser procesamiento de APIs.
- **APIs externas:** Google, Kling AI (video desde imagen), Text-to-Audio, Shotstack (render de video).
- **Patrones clave (varios muy valiosos):**
  - **Cadena con handoff de datos:** la salida del Agente 1 (script + clips + audio) es la entrada del Agente 2 (ensamblado final).
  - **Modelo por agente según tarea:** modelo fuerte para creatividad, modelo barato para procesar APIs → optimiza costo sin perder calidad. (Confirma nuestra estrategia de costos.)
  - **Integración de APIs externas** para capacidades que el LLM no tiene (render de video, generación de video/audio).
  - **Formato de prompt claro:** Rol → SOP/instrucciones numeradas → qué herramienta usar en cada paso → formato de salida esperado → ejemplos de JSON. ← adoptamos ESTE formato (no su contenido) como estándar para escribir nuestros prompts.
- **Aplicación nuestra:** modelo directo para el agente 7 (Fragmentador/Generador de video). Para fragmentar contenido del ecosistema (Portal Kumaras, Mahatma 441) en reels usaríamos un patrón similar: agente creativo + agente ensamblador con API de render.

> Nota: el documento de Fabián incluye los prompts textuales del creador original. NO se copian; se usan solo como referencia de estructura. Nuestros prompts se escriben originales y adaptados al cliente.

---

## 6. Competitor Spy
- **Enfoque:** inteligencia competitiva multicanal (Meta Ads, Google Ads, sitios web) en un reporte unificado.
- **Arquitectura — orquestador + 3 subordinados (patrón director en su forma más clara):**
  - **Centro de Inteligencia Competitiva** (orquestador): coordina a los 3 y produce un informe único.
  - **Meta Ads Spy:** monitorea anuncios de la Meta Ads Library y detecta cambios. Tools: scraper de Meta Ads, analizador visual de creatividades, Snapshot Manager, detector de cambios.
  - **Google Ads Spy:** analiza anuncios del Google Ads Transparency Center. Tool: Google Ads Spy.
  - **Website Monitor:** vigila sitios de la competencia (screenshots, cambios de sitemap, páginas nuevas).
- **Modelo:** todos en Claude Sonnet 4.
- **Patrones clave (el más nuevo y valioso del lote):**
  - **Gestión de estado / snapshots:** flujo por ejecución = obtener snapshot previo → scrapear actual → detectar cambios → guardar snapshot → reportar. Permite **detección incremental de cambios entre ejecuciones** (qué es nuevo, qué desapareció). Ideal para tareas recurrentes/monitoreo.
  - **Orquestador que delega** en subordinados especializados y consolida en un solo reporte (patrón director = nuestro CEO/MRP).
  - **Insights accionables > datos brutos:** salida siempre con resumen ejecutivo → análisis → oportunidades → acciones recomendadas.
  - **Input flexible:** si falta el parámetro (ej. competidor), se extrae del mensaje del usuario.
- **Aplicación nuestra:** modelo directo para el agente 12 (Analista de métricas) y para ofrecer a clientes un agente de espionaje competitivo. El patrón de snapshots sirve a cualquier agente de monitoreo recurrente (campañas, precios, contenido).

---

## Cierre — las 6 arquitecturas de referencia (completo)

| # | Workforce | Patrón que aporta |
|---|---|---|
| 1 | Multi-Platform | Amplio multi-servicio + orquestador (MRP Manager) |
| 2 | GSuite | Especializado y simple + Manager |
| 3 | AI Content Writing Team | Equipo de contenido en cadena + agente consolidador |
| 4 | Instant Lead List Generator | Pipeline minimalista crudo→limpio→JSON (mejor puntuado) |
| 5 | Tari-AI-ntino Video | Cadena creativa + ensamblador; modelo por agente; APIs externas |
| 6 | Competitor Spy | Orquestador + subordinados; gestión de estado/snapshots; insights accionables |

**Síntesis de principios para crear nuestros agentes:** arquitectura > cantidad de tools; pipelines/cadenas con handoff limpio; un orquestador que delega y consolida; modelo fuerte solo donde aporta y barato en lo mecánico; gestión de estado para monitoreo recurrente; salida estructurada y accionable. Prompts propios (formato Rol→SOP→tools→salida→ejemplos), nunca copiados.

> Los prompts textuales que trajo Fabián se usan solo como referencia de estructura; los nuestros van originales y adaptados a cada cliente.
