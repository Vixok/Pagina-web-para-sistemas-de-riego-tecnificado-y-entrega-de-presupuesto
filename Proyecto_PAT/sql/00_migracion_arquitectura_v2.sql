USE PAT_RIEGO;
GO
SET XACT_ABORT ON;
GO

-- ============================================================
-- PAT_RIEGO V2 - MIGRACIÓN INCREMENTAL E IDEMPOTENTE
-- Preserva IDs maestros y agrega arquitectura 4 -> 8.
-- ============================================================

-- ---------- Blindaje catálogo Bombas ----------
IF COL_LENGTH('dbo.Bombas','codigo_bomba') IS NULL
    ALTER TABLE dbo.Bombas ADD codigo_bomba NVARCHAR(30) NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name='UX_Bombas_codigo_bomba' AND object_id=OBJECT_ID('dbo.Bombas')
)
CREATE UNIQUE INDEX UX_Bombas_codigo_bomba
ON dbo.Bombas(codigo_bomba)
WHERE codigo_bomba IS NOT NULL;
GO

-- ---------- Blindaje otros catálogos ----------
IF COL_LENGTH('dbo.Tuberias','codigo_tubo') IS NULL
    ALTER TABLE dbo.Tuberias ADD codigo_tubo NVARCHAR(30) NULL;
GO
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name='UX_Tuberias_codigo_tubo' AND object_id=OBJECT_ID('dbo.Tuberias')
)
CREATE UNIQUE INDEX UX_Tuberias_codigo_tubo ON dbo.Tuberias(codigo_tubo) WHERE codigo_tubo IS NOT NULL;
GO

IF COL_LENGTH('dbo.Emisores','codigo_emisor') IS NULL
    ALTER TABLE dbo.Emisores ADD codigo_emisor NVARCHAR(30) NULL;
GO
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name='UX_Emisores_codigo_emisor' AND object_id=OBJECT_ID('dbo.Emisores')
)
CREATE UNIQUE INDEX UX_Emisores_codigo_emisor ON dbo.Emisores(codigo_emisor) WHERE codigo_emisor IS NOT NULL;
GO

-- ---------- Histórico de cotizaciones ----------
IF OBJECT_ID('dbo.CotizacionesBombasMercado','U') IS NULL
BEGIN
    CREATE TABLE dbo.CotizacionesBombasMercado (
        id_cotizacion INT IDENTITY(1,1) PRIMARY KEY,
        id_bomba INT NOT NULL,
        consulta_busqueda NVARCHAR(1000) NULL,
        fuente NVARCHAR(150) NULL,
        producto NVARCHAR(1000) NULL,
        precio_clp DECIMAL(18,2) NULL,
        url NVARCHAR(2000) NULL,
        score_coincidencia DECIMAL(8,2) NULL,
        caudal_requerido_ls DECIMAL(14,4) NULL,
        tdh_requerida_mca DECIMAL(14,4) NULL,
        fecha_consulta DATETIME2 NOT NULL CONSTRAINT DF_CotBombas_Fecha DEFAULT SYSDATETIME(),
        valida BIT NOT NULL CONSTRAINT DF_CotBombas_Valida DEFAULT 0,
        CONSTRAINT FK_CotBombas_Bombas FOREIGN KEY(id_bomba) REFERENCES dbo.Bombas(id_bomba)
    );
END;
GO
-- Si la tabla ya existía en una versión previa, completar columnas faltantes sin borrar datos.
IF COL_LENGTH('dbo.CotizacionesBombasMercado','consulta_busqueda') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD consulta_busqueda NVARCHAR(1000) NULL;
IF COL_LENGTH('dbo.CotizacionesBombasMercado','fuente') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD fuente NVARCHAR(150) NULL;
IF COL_LENGTH('dbo.CotizacionesBombasMercado','producto') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD producto NVARCHAR(1000) NULL;
IF COL_LENGTH('dbo.CotizacionesBombasMercado','precio_clp') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD precio_clp DECIMAL(18,2) NULL;
IF COL_LENGTH('dbo.CotizacionesBombasMercado','url') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD url NVARCHAR(2000) NULL;
IF COL_LENGTH('dbo.CotizacionesBombasMercado','score_coincidencia') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD score_coincidencia DECIMAL(8,2) NULL;
IF COL_LENGTH('dbo.CotizacionesBombasMercado','caudal_requerido_ls') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD caudal_requerido_ls DECIMAL(14,4) NULL;
IF COL_LENGTH('dbo.CotizacionesBombasMercado','tdh_requerida_mca') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD tdh_requerida_mca DECIMAL(14,4) NULL;
IF COL_LENGTH('dbo.CotizacionesBombasMercado','fecha_consulta') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD fecha_consulta DATETIME2 NULL;
IF COL_LENGTH('dbo.CotizacionesBombasMercado','valida') IS NULL ALTER TABLE dbo.CotizacionesBombasMercado ADD valida BIT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_CotBombas_BombaFecha' AND object_id=OBJECT_ID('dbo.CotizacionesBombasMercado'))
CREATE INDEX IX_CotBombas_BombaFecha ON dbo.CotizacionesBombasMercado(id_bomba, fecha_consulta DESC) INCLUDE(precio_clp, valida, score_coincidencia);
GO

-- ---------- Paso 5: curvas Q-H ----------
IF OBJECT_ID('dbo.CurvasBombas','U') IS NULL
BEGIN
    CREATE TABLE dbo.CurvasBombas (
        id_punto INT IDENTITY(1,1) PRIMARY KEY,
        id_bomba INT NOT NULL,
        caudal_lmin DECIMAL(14,4) NOT NULL,
        altura_mca DECIMAL(14,4) NOT NULL,
        eficiencia_pct DECIMAL(10,3) NULL,
        potencia_kw DECIMAL(12,4) NULL,
        fecha_fuente DATETIME2 NOT NULL CONSTRAINT DF_CurvasBombas_Fecha DEFAULT SYSDATETIME(),
        fuente NVARCHAR(500) NULL,
        validada BIT NOT NULL CONSTRAINT DF_CurvasBombas_Validada DEFAULT 0,
        activo BIT NOT NULL CONSTRAINT DF_CurvasBombas_Activo DEFAULT 1,
        CONSTRAINT FK_CurvasBombas_Bombas FOREIGN KEY(id_bomba) REFERENCES dbo.Bombas(id_bomba),
        CONSTRAINT CK_CurvasBombas_Q CHECK (caudal_lmin >= 0),
        CONSTRAINT CK_CurvasBombas_H CHECK (altura_mca >= 0)
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_CurvasBombas_BombaQ' AND object_id=OBJECT_ID('dbo.CurvasBombas'))
CREATE INDEX IX_CurvasBombas_BombaQ ON dbo.CurvasBombas(id_bomba, caudal_lmin) INCLUDE(altura_mca, eficiencia_pct, validada, activo);
GO

-- ---------- Segunda capa: candidatos web ----------
IF OBJECT_ID('dbo.CandidatosBombasWeb','U') IS NULL
BEGIN
    CREATE TABLE dbo.CandidatosBombasWeb (
        id_candidato INT IDENTITY(1,1) PRIMARY KEY,
        producto NVARCHAR(1000) NULL,
        marca NVARCHAR(200) NULL,
        modelo_detectado NVARCHAR(500) NULL,
        potencia_detectada_hp DECIMAL(12,3) NULL,
        caudal_detectado_ls DECIMAL(14,4) NULL,
        altura_detectada_mca DECIMAL(14,4) NULL,
        precio_clp DECIMAL(18,2) NULL,
        fuente NVARCHAR(150) NULL,
        url NVARCHAR(2000) NULL,
        score_coincidencia DECIMAL(8,2) NULL,
        consulta_busqueda NVARCHAR(1000) NULL,
        estado NVARCHAR(30) NOT NULL CONSTRAINT DF_CandidatosBombasWeb_Estado DEFAULT 'REVISAR',
        fecha_consulta DATETIME2 NOT NULL CONSTRAINT DF_CandidatosBombasWeb_Fecha DEFAULT SYSDATETIME(),
        fecha_respuesta DATETIME2 NULL,
        CONSTRAINT CK_CandidatosBombasWeb_Estado CHECK (estado IN ('DESCARTADO','REVISAR','PENDIENTE_HITL','APROBADO','RECHAZADO','INCORPORADO'))
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_CandidatosBombasWeb_EstadoFecha' AND object_id=OBJECT_ID('dbo.CandidatosBombasWeb'))
CREATE INDEX IX_CandidatosBombasWeb_EstadoFecha ON dbo.CandidatosBombasWeb(estado, fecha_consulta DESC);
GO

-- ---------- Selección de bombas: trazabilidad técnica ----------
IF COL_LENGTH('dbo.SeleccionBombas','q_operacion_ls') IS NULL
    ALTER TABLE dbo.SeleccionBombas ADD q_operacion_ls DECIMAL(14,4) NULL;
IF COL_LENGTH('dbo.SeleccionBombas','h_operacion_mca') IS NULL
    ALTER TABLE dbo.SeleccionBombas ADD h_operacion_mca DECIMAL(14,4) NULL;
IF COL_LENGTH('dbo.SeleccionBombas','curva_validada') IS NULL
    ALTER TABLE dbo.SeleccionBombas ADD curva_validada BIT NULL;
IF COL_LENGTH('dbo.SeleccionBombas','estado_validacion') IS NULL
    ALTER TABLE dbo.SeleccionBombas ADD estado_validacion NVARCHAR(40) NULL;
IF COL_LENGTH('dbo.SeleccionBombas','score_tecnico_economico') IS NULL
    ALTER TABLE dbo.SeleccionBombas ADD score_tecnico_economico DECIMAL(12,6) NULL;
IF COL_LENGTH('dbo.SeleccionBombas','fuente_precio') IS NULL
    ALTER TABLE dbo.SeleccionBombas ADD fuente_precio NVARCHAR(250) NULL;
IF COL_LENGTH('dbo.SeleccionBombas','version_algoritmo') IS NULL
    ALTER TABLE dbo.SeleccionBombas ADD version_algoritmo NVARCHAR(50) NULL;
GO

-- ---------- Paso 7: agente + HITL ----------
IF COL_LENGTH('dbo.EjecucionesAgente','version_algoritmo') IS NULL
    ALTER TABLE dbo.EjecucionesAgente ADD version_algoritmo NVARCHAR(50) NULL;
GO
IF COL_LENGTH('dbo.AprobacionesHITL','accion_solicitada') IS NULL
    ALTER TABLE dbo.AprobacionesHITL ADD accion_solicitada NVARCHAR(250) NULL;
IF COL_LENGTH('dbo.AprobacionesHITL','resultado_previo') IS NULL
    ALTER TABLE dbo.AprobacionesHITL ADD resultado_previo NVARCHAR(MAX) NULL;
IF COL_LENGTH('dbo.AprobacionesHITL','resultado_aprobado') IS NULL
    ALTER TABLE dbo.AprobacionesHITL ADD resultado_aprobado NVARCHAR(MAX) NULL;
GO

-- ---------- Paso 8: Monte Carlo ----------
IF OBJECT_ID('dbo.SimulacionesMonteCarlo','U') IS NULL
BEGIN
    CREATE TABLE dbo.SimulacionesMonteCarlo (
        id_simulacion INT IDENTITY(1,1) PRIMARY KEY,
        id_proyecto INT NOT NULL,
        n_iteraciones INT NOT NULL,
        seed INT NOT NULL,
        variables_json NVARCHAR(MAX) NULL,
        parametros_json NVARCHAR(MAX) NULL,
        estado NVARCHAR(30) NOT NULL CONSTRAINT DF_SimMC_Estado DEFAULT 'COMPLETADA',
        fecha DATETIME2 NOT NULL CONSTRAINT DF_SimMC_Fecha DEFAULT SYSDATETIME(),
        CONSTRAINT FK_SimMC_Proyecto FOREIGN KEY(id_proyecto) REFERENCES dbo.Proyectos(id_proyecto)
    );
END;
GO
IF OBJECT_ID('dbo.ResultadosMonteCarlo','U') IS NULL
BEGIN
    CREATE TABLE dbo.ResultadosMonteCarlo (
        id_resultado_mc INT IDENTITY(1,1) PRIMARY KEY,
        id_simulacion INT NOT NULL,
        media_clp DECIMAL(20,2) NULL,
        desviacion_clp DECIMAL(20,2) NULL,
        p05_clp DECIMAL(20,2) NULL,
        p10_clp DECIMAL(20,2) NULL,
        p50_clp DECIMAL(20,2) NULL,
        p80_clp DECIMAL(20,2) NULL,
        p90_clp DECIMAL(20,2) NULL,
        p95_clp DECIMAL(20,2) NULL,
        prob_excedencia_pct DECIMAL(10,4) NULL,
        presupuesto_objetivo_clp DECIMAL(20,2) NULL,
        CONSTRAINT FK_ResultMC_Sim FOREIGN KEY(id_simulacion) REFERENCES dbo.SimulacionesMonteCarlo(id_simulacion)
    );
END;
GO

-- ---------- Registro de versión de esquema ----------
IF OBJECT_ID('dbo.VersionesEsquemaPAT','U') IS NULL
BEGIN
    CREATE TABLE dbo.VersionesEsquemaPAT (
        id_version INT IDENTITY(1,1) PRIMARY KEY,
        version_codigo NVARCHAR(50) NOT NULL UNIQUE,
        descripcion NVARCHAR(500) NULL,
        fecha_aplicacion DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM dbo.VersionesEsquemaPAT WHERE version_codigo='PAT-V2-4A8')
INSERT INTO dbo.VersionesEsquemaPAT(version_codigo, descripcion)
VALUES ('PAT-V2-4A8','Blindaje IDs + optimizador serie/paralelo + curvas Q-H + candidatos web/HITL + histórico + agente + Monte Carlo');
GO

SELECT 'PAT-V2-4A8' AS version_aplicada, SYSDATETIME() AS fecha;
GO
