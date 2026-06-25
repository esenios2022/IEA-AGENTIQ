# IEA AGENTIQ - Agentes Exportables

## 📋 16 AGENTES CREADOS Y LISTOS

Todos los agentes están en formato JSON en `agents_config.json` y pueden ser importados a:
- ✅ **Supabase** (PostgreSQL)
- ✅ **CrewAI** (cuando esté integrado)
- ✅ **Cualquier otra plataforma** (JSON es estándar)

### Agentes por Máquina:

#### **Máquina de Adquisición**
1. Inteligencia en Negocios
2. Prospección en LinkedIn
3. Gestor de Ventas

#### **Máquina de Contenido**
4. Gestor de Redes Sociales
5. Estratega de Marketing
6. Especialista en SEO
7. Especialista en Diseño

#### **Máquina de Atención**
8. Soporte de Atención al Cliente

#### **Máquina de Operaciones**
9. Contabilidad y Finanzas
10. Automatización de Flujos
11. Gestor de Proyectos
12. Especialista en RH
13. Gestor de Integraciones

#### **Máquina de Cumplimiento**
14. Asesor Legal

#### **Máquina de Análisis**
15. Especialista en Datos

#### **Máquina de Calidad**
16. Coordinador de Calidad

---

## 🔗 CÓMO IMPORTAR A SUPABASE

```bash
cd backend
python import_agents.py
```

Esto:
1. ✅ Lee `agents_config.json`
2. ✅ Crea los 16 agentes en Supabase
3. ✅ Configura 9 herramientas
4. ✅ Los deja listos en la BD

---

## 📦 ESTRUCTURA JSON

Cada agente tiene:
```json
{
  "id": "agent_001",
  "name": "Nombre",
  "role": "Role en inglés",
  "goal": "Objetivo",
  "prompt": "Instrucción detallada",
  "group": "Máquina",
  "tools": ["herramienta1", "herramienta2"],
  "language": "es/pt",
  "status": "active"
}
```

---

## 🔐 HERRAMIENTAS CONFIGURADAS

| Herramienta | Proveedor | Estado | API Key |
|---|---|---|---|
| Web Search | Google | Pending | ✅ |
| LinkedIn | LinkedIn API | Pending | ✅ |
| WhatsApp | WhatsApp Business | Pending | ✅ |
| Email | Gmail API | Pending | ✅ |
| CRM | Custom | Pending | ✅ |
| Zapier | Zapier | Pending | ✅ |
| File Management | Supabase Storage | Ready | ❌ |
| Data Analysis | Custom | Ready | ❌ |
| Content Generation | OpenAI | Pending | ✅ |

---

## ⚡ PRÓXIMO PASO

Cuando CrewAI esté integrado, se conectarán automáticamente a estos agentes.

¿Vamos con CrewAI ahora?
