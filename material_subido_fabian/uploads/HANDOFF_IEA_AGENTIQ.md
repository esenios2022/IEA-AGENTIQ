# HANDOFF — Proyecto IEA AGENTIQ
### Documento de traspaso para continuar en otro Claude (Code / Design / chat nuevo)
Pegá este archivo o abrílo en el otro Claude para que retome el proyecto con todo el contexto.

---

## 1. Qué es el proyecto
**IEA AGENTIQ** es una plataforma (tipo Relevance AI, pero más simple) para **vender y operar agentes de IA**. Se vende junto con los agentes que diseña Fabián. Carpeta del proyecto: "AgentiQ TVD".

> Importante: **IEA AGENTIQ = la plataforma/producto**. **EA Lumina = uno de los clientes** (negocio terapéutico de Fabián, mercado Brasil). NO todos los agentes son terapéuticos: antes de crear agentes, SIEMPRE preguntar para qué cliente/negocio son.

## 2. La propuesta / lema
"Máquina de adquisición autónoma": agentes que hacen el embudo completo (captar leads → contactar por email/WhatsApp → vender) + contenido en redes, y el cliente solo aprueba (sí/no) como CEO.
Lema: **"Libertad total. Sé el director ejecutivo de tu negocio. Recuperá tu tiempo, tu salud, tu paz — sin dejar tu negocio."**
Mercados: Brasil primero (PT-BR), luego Uruguay y Argentina (ES).

## 3. Modelo de precios (CERRADO)
- Cada agente: **USD 39/mes**. Plan = 39 × cantidad de agentes (1→$39, 3→$117, 6→$234, 9→$351, todos→39×total).
- Multiplicador por plazo: **anual x1 ($39) · semestral x1.5 ($58.50) · mensual/1 mes x2 ($78)**.
- Planes: permanencia mínima 6 meses; el cliente puede subir/bajar de plan.
- Agente extra del catálogo: mínimo 1 mes, mismo esquema de plazos. El cliente lo solicita → llega email al equipo → lo programan y activan → avisan por email. Se suma a su cuenta y consumo.
- Tokens/consumo: aparte; el cliente puede poner su propia API key.

## 4. Los 12 agentes (máquina de adquisición)
1 Prospector LinkedIn · 2 Prospector IG+Facebook · 3 Calificador de leads · 4 Redactor de invitaciones · 5 Limpiador de listas WhatsApp · 6 Difusor WhatsApp · 7 Fragmentador de video · 8 Generador de copy+hashtags · 9 Publicador omnicanal · 10 Primer contacto B2C · 11 Seguimiento/nurturing · 12 Analista de métricas.

## 5. Cómo se crean los agentes (reglas)
- **Preguntar primero el cliente** (no asumir terapéutico).
- Prompts **originales** (las plantillas de Relevance/Pickaxe solo de referencia, NO copiar).
- Bilingües **PT-BR + ES**.
- Formato de prompt: **Rol → SOP (pasos numerados) → qué herramienta en cada paso → formato de salida → ejemplos**.
- Modelo por tarea: barato (GPT-5 Nano / Gemini Flash-Lite / Haiku) para lo mecánico; fuerte (Sonnet/Opus) solo para creatividad/razonamiento.
- Base común: todos heredan capacidades (bilingüe, registro de pasos legible, aprobación humana, medición de costo, memoria, manejo de errores, límite de gasto) y una caja de herramientas (web, email, WhatsApp API oficial, LinkedIn, enriquecedor de leads, CRM, archivos, agenda, generación de contenido).
- Patrón orquestador: un agente "director" coordina a los demás (workforce).
- Nivel objetivo: agentes nivel 4 (autónomos, proactivos, 24/7 — según infraestructura), con aprobación humana para acciones sensibles.
- Cumplimiento: LGPD Brasil, WhatsApp Business API oficial / warmup / opt-in, anti-spam email.

## 6. La plataforma (prototipo ya construido)
Archivo: **`IEA_AGENTIQ_Plataforma.html`** (maqueta funcional, una sola página, datos de ejemplo). Tiene:
- Dos vistas: **Cliente** (simple) y **Admin** (consola completa).
- Menú lateral estilo programa: Inicio, Chat, Agentes (con actividad paso a paso), Equipos/Workforces, Clientes, Ejecuciones, Herramientas, Rentabilidad, Analítica, Catálogo, Historial, Conexión & API, Conocimiento, **Funciones**, Ayuda.
- **Chat** para darle órdenes al agente.
- **Catálogo**: el cliente contrata agentes por 1 mes / 6 meses / año.
- **Consumo** con proyección de fin de mes; **Rentabilidad** (ingresos − costo = ganancia) para el admin.
- **Analítica** con gráficas.
- **Gating**: el admin habilita/deshabilita funciones por cliente. Catálogo de funciones (Bandeja unificada, Agenda, Seguimiento, Cobros, Publicar, Reporte semanal, Voz clonada, Asistente proactivo, Alertas, Base de conocimiento, Encuestas, Flujos) + futuras bloqueadas "Próximamente" (Portal con marca, Página pública, Monetización — inspiradas en Pickaxe).
- **Asistente de ayuda** tipo Claude en Chrome (panel lateral derecho, contextual, responde en el idioma activo).
- **Bilingüe ES/PT** con botones ES|PT e idioma automático por país del cliente.
- Identidad visual: **esmeralda (#0b4d3c) + crema + dorado sobrio (#b08d57)**, unificada con la landing. (A Fabián NO le gusta el oro brillante ni los iconos genéricos.)

## 7. Otros archivos en la carpeta
- `IEA_AGENTIQ_Landing.html` — página de venta (del repo, rama claude/optimistic-dirac-fre3zt) con botón "Entrar a la plataforma".
- Documentos de referencia: `Estructura_Base_Agentes.md`, `Catalogo_Tools_Integraciones_Workforce.md`, `Workforces_Referencia_Relevance.md`, `Top15_Agentes_Relevance.md`, `Referencia_Agentes_Relevance.md`, `EA_Lumina_Agent_Workspace_Plan.docx`.
- Repo GitHub `esenios2022/iea-agentiq`: backend FastAPI (src/) + landing. La carpeta local NO es git todavía.

## 8. Entrega: web + escritorio
Mismo código sirve para **web** (navegador; integrable al sitio del cliente vía iframe, subdominio o "Portal con su marca") y **escritorio** (app instalable; ya hay base **Tauri** en el repo). Los agentes corren en el SERVIDOR, no en la PC → el costo de tokens es igual en web o escritorio.

## 9. PRÓXIMO PASO acordado
Dejar de agrandar la maqueta y **construir el primer agente real para EA Lumina: el Fragmentador de video** (corta clases de Portal Kumaras / Mahatma 441 en reels), elegido porque NO depende de aprobaciones lentas de WhatsApp. Escribirlo con el formato de la sección 5 (Rol→SOP→herramientas→salida), prompt original PT-BR + ES, herramientas: transcribir → detectar clips → generar copy → ensamblador con API de render (tipo Shotstack). Después: backend real + base de datos.

---
*Fin del traspaso. Cualquier Claude que lea esto puede continuar el proyecto sin perder el hilo.*
