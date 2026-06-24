# IEA AGENTIQ - Setup Completo

## ✅ QUÉ SE ACABA DE CREAR

### Backend (FastAPI + PostgreSQL)
```
backend/
├── app/
│   ├── main.py          (Rutas API)
│   ├── models.py        (Base de datos)
│   ├── schemas.py       (Validación de datos)
│   └── database.py      (Conexión Supabase)
├── migrations/
│   └── 001_create_tables.sql
├── requirements.txt
└── .env.example
```

### Frontend
```
frontend/
├── IEA_AGENTIQ_Landing.html    (Landing page)
├── IEA_AGENTIQ_Plataforma.html (Plataforma admin)
└── Dashboard.html              (Dashboard de agentes)
```

---

## 🚀 INSTALACIÓN

### 1. Clonar repo
```bash
git clone https://github.com/esenios2022/IEA-AGENTIQ.git
cd IEA-AGENTIQ
```

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Copiar .env
cp .env.example .env
# Editar .env con tu contraseña de Supabase

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
uvicorn app.main:app --reload
```

### 3. Supabase
1. Ve a https://supabase.com/dashboard/project/djyuotgzcwhqvoowvixv
2. Abre SQL Editor
3. Copia el contenido de `backend/migrations/001_create_tables.sql`
4. Ejecuta

### 4. Frontend
```bash
cd frontend
# Abrir IEA_AGENTIQ_Landing.html en navegador
# O usar: python -m http.server 8080
```

---

## 📊 RUTAS API DISPONIBLES

### Agentes
- `POST /api/agents` - Crear agente
- `GET /api/agents` - Listar agentes
- `GET /api/agents/{id}` - Obtener detalle
- `PUT /api/agents/{id}` - Editar agente
- `DELETE /api/agents/{id}` - Eliminar agente
- `POST /api/agents/{id}/run` - Ejecutar agente

### Clientes
- `POST /api/clients` - Crear cliente
- `GET /api/clients` - Listar clientes

### Ejecuciones
- `GET /api/executions/{id}` - Obtener ejecución
- `GET /api/executions/{id}/logs` - Obtener logs

### Leads
- `POST /api/leads` - Crear lead
- `GET /api/leads` - Listar leads

---

## 🔄 PRÓXIMOS PASOS

1. **Integrar CrewAI** en `app/main.py`
2. **Conectar herramientas reales** (LinkedIn, WhatsApp, etc)
3. **WebSocket para logs en tiempo real**
4. **Frontend mejorado** con React/Vue
5. **Deploy a Vercel/Railway**

---

## ❓ PREGUNTAS

¿Necesitas que empecemos con CrewAI ahora?
