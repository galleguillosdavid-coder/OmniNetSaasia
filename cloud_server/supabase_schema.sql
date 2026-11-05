-- ============================================================================
-- OMNINET AI AGENT PRO - SCHEMA SUPABASE / POSTGRESQL (SaaS MUNDIAL)
-- Copia y pega este script en el "SQL Editor" de tu proyecto en Supabase
-- ============================================================================

-- 1. EXTENSIÓN PARA UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. TABLA DE LICENCIAS Y SUSCRIPCIONES
CREATE TABLE IF NOT EXISTS public.licenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    license_key VARCHAR(64) UNIQUE NOT NULL,
    plan VARCHAR(32) NOT NULL DEFAULT 'pro',           -- 'free', 'pro', 'family'
    email VARCHAR(255) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    max_devices INT NOT NULL DEFAULT 1,                -- Pro = 1 PC, Family = 5 PCs
    devices JSONB NOT NULL DEFAULT '[]'::jsonb,        -- Lista de Hardware IDs registrados
    queries_count BIGINT NOT NULL DEFAULT 0,          -- Contador de consultas proxied
    payment_provider VARCHAR(32) DEFAULT 'lemon_squeezy', -- 'lemon_squeezy', 'stripe'
    subscription_id VARCHAR(128),                      -- ID de Lemon Squeezy / Stripe
    expires_at TIMESTAMPTZ,                            -- Fecha de vencimiento si cancela
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices de alto rendimiento para búsqueda instantánea
CREATE INDEX IF NOT EXISTS idx_licenses_key ON public.licenses(license_key);
CREATE INDEX IF NOT EXISTS idx_licenses_email ON public.licenses(email);

-- 3. TABLA DE RETROALIMENTACIÓN ANÓNIMA DE CONVERSACIONES (APRENDIZAJE IA)
CREATE TABLE IF NOT EXISTS public.conversations_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id VARCHAR(128),
    license_key VARCHAR(64),
    user_message TEXT NOT NULL,
    ai_reply TEXT,
    satisfaction_rating INT,                           -- 1 a 5 estrellas (opcional)
    latency_ms NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_created ON public.conversations_feedback(created_at DESC);

-- 4. TABLA DE EVENTOS DE PAGO (WEBHOOKS AUDIT TRAIL)
CREATE TABLE IF NOT EXISTS public.payment_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(64) NOT NULL,                   -- 'order_created', 'subscription_renewed', etc.
    provider VARCHAR(32) NOT NULL,                     -- 'lemon_squeezy', 'stripe'
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. SEMILLA DE LICENCIAS MAESTRAS INICIALES
INSERT INTO public.licenses (license_key, plan, email, active, max_devices, devices)
VALUES 
    ('OMNI-PRO-MASTER-2026', 'pro', 'founder@omninet.ai', TRUE, 10, '[]'::jsonb),
    ('OMNI-PRO-DEMO-2026', 'pro', 'demo@omninet.ai', TRUE, 1, '[]'::jsonb)
ON CONFLICT (license_key) DO NOTHING;

-- 6. POLÍTICAS DE SEGURIDAD (ROW LEVEL SECURITY - RLS)
ALTER TABLE public.licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_events ENABLE ROW LEVEL SECURITY;

-- Acceso seguro: Solo el servidor backend (service_role) puede leer y escribir libremente
CREATE POLICY "Service Role Full Access Licenses" 
ON public.licenses 
FOR ALL 
TO service_role 
USING (true) 
WITH CHECK (true);

CREATE POLICY "Service Role Full Access Feedback" 
ON public.conversations_feedback 
FOR ALL 
TO service_role 
USING (true) 
WITH CHECK (true);

CREATE POLICY "Service Role Full Access Payment Events" 
ON public.payment_events 
FOR ALL 
TO service_role 
USING (true) 
WITH CHECK (true);

