-- =============================================================================
-- PATCH 012 — Catálogo de marcas de carro (para compatibilidad / repuestos)
-- Ejecutar una vez en Supabase SQL Editor.
-- La app puede leer `marcas_vehiculo` y armar multiselect o sugerencias;
-- en `productos.compatibilidad` seguís guardando JSON (marcas_vehiculo, años).
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.marcas_vehiculo (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre TEXT NOT NULL,
  orden INT NOT NULL DEFAULT 0,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT marcas_vehiculo_nombre_unique UNIQUE (nombre)
);

CREATE INDEX IF NOT EXISTS idx_marcas_vehiculo_activo_orden
  ON public.marcas_vehiculo (activo, orden, nombre);

COMMENT ON TABLE public.marcas_vehiculo IS 'Marcas de vehículo para compatibilidad de repuestos (catálogo maestro).';

-- Idempotente: no duplica si ya existía la marca
INSERT INTO public.marcas_vehiculo (nombre, orden) VALUES
  ('Acura', 10),
  ('Alfa Romeo', 20),
  ('Aro', 25),
  ('Audi', 30),
  ('BAIC', 40),
  ('Bentley', 50),
  ('BMW', 60),
  ('Brilliance', 70),
  ('Buick', 80),
  ('BYD', 90),
  ('Cadillac', 100),
  ('Changan', 110),
  ('Chery', 120),
  ('Chevrolet', 130),
  ('Chrysler', 140),
  ('Citroën', 150),
  ('Dacia', 160),
  ('DFSK', 170),
  ('Dodge', 180),
  ('Dongfeng', 190),
  ('Ferrari', 200),
  ('Fiat', 210),
  ('Ford', 220),
  ('Foton', 230),
  ('GAC', 240),
  ('Geely', 250),
  ('Genesis', 260),
  ('GMC', 270),
  ('Great Wall', 280),
  ('Haval', 290),
  ('Honda', 300),
  ('Hummer', 310),
  ('Hyundai', 320),
  ('Infiniti', 330),
  ('Isuzu', 340),
  ('Iveco', 350),
  ('JAC', 360),
  ('Jaguar', 370),
  ('Jeep', 380),
  ('JMC', 390),
  ('Kia', 400),
  ('Lada', 410),
  ('Lamborghini', 420),
  ('Lancia', 430),
  ('Land Rover', 440),
  ('Lexus', 450),
  ('Lifan', 460),
  ('Lincoln', 470),
  ('Lotus', 480),
  ('Mahindra', 490),
  ('Maserati', 500),
  ('Mazda', 510),
  ('McLaren', 520),
  ('Mercedes-Benz', 530),
  ('Mercury', 540),
  ('MG', 550),
  ('Mini', 560),
  ('Mitsubishi', 570),
  ('Nissan', 580),
  ('Opel', 590),
  ('Peugeot', 600),
  ('Porsche', 610),
  ('RAM', 620),
  ('Renault', 630),
  ('Rolls-Royce', 640),
  ('Rover', 650),
  ('Saab', 660),
  ('Scania', 670),
  ('SEAT', 680),
  ('Skoda', 690),
  ('Smart', 700),
  ('SsangYong', 710),
  ('Subaru', 720),
  ('Suzuki', 730),
  ('Tata', 740),
  ('Tesla', 750),
  ('Toyota', 760),
  ('Volkswagen', 770),
  ('Volvo', 780),
  ('Wuling', 790),
  ('ZNA', 800),
  ('ZX Auto', 810)
ON CONFLICT (nombre) DO NOTHING;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.marcas_vehiculo TO service_role;

NOTIFY pgrst, 'reload schema';
