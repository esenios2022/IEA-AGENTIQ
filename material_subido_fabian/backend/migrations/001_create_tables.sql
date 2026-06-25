-- IEA AGENTIQ DATABASE SCHEMA
-- Supabase: djyuotgzcwhqvoowvixv

-- 1. TABLA: AGENTES
CREATE TABLE IF NOT EXISTS agents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  role VARCHAR(100) NOT NULL,
  goal TEXT,
  prompt TEXT,
  tools JSONB DEFAULT '[]'::jsonb,
  status VARCHAR(50) DEFAULT 'active',
  group_name VARCHAR(100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. TABLA: CLIENTES
CREATE TABLE IF NOT EXISTS clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  plan VARCHAR(50) DEFAULT 'starter',
  agents_count INT DEFAULT 0,
  status VARCHAR(50) DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. TABLA: ASIGNACIONES (Qué cliente tiene qué agentes)
CREATE TABLE IF NOT EXISTS client_agents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
  agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
  assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(client_id, agent_id)
);

-- 4. TABLA: EJECUCIONES
CREATE TABLE IF NOT EXISTS executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
  client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
  start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  end_time TIMESTAMP WITH TIME ZONE,
  status VARCHAR(50) DEFAULT 'running',
  result JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. TABLA: LOGS EN TIEMPO REAL
CREATE TABLE IF NOT EXISTS logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id UUID REFERENCES executions(id) ON DELETE CASCADE,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  level VARCHAR(20) DEFAULT 'info',
  message TEXT
);

-- 6. TABLA: HERRAMIENTAS
CREATE TABLE IF NOT EXISTS tools (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL UNIQUE,
  description TEXT,
  type VARCHAR(50),
  config JSONB DEFAULT '{}'::jsonb,
  status VARCHAR(50) DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. TABLA: LEADS (existente)
CREATE TABLE IF NOT EXISTS leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) NOT NULL,
  name VARCHAR(255),
  message TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ÍNDICES
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_group ON agents(group_name);
CREATE INDEX IF NOT EXISTS idx_executions_agent ON executions(agent_id);
CREATE INDEX IF NOT EXISTS idx_executions_client ON executions(client_id);
CREATE INDEX IF NOT EXISTS idx_logs_execution ON logs(execution_id);
CREATE INDEX IF NOT EXISTS idx_client_agents ON client_agents(client_id, agent_id);

-- ENABLE ROW LEVEL SECURITY
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;
