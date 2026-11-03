USE PAT_RIEGO;
GO

SELECT version_codigo, descripcion, fecha_aplicacion
FROM dbo.VersionesEsquemaPAT
ORDER BY fecha_aplicacion DESC;

SELECT name
FROM sys.tables
WHERE name IN (
    'Bombas','CotizacionesBombasMercado','CurvasBombas','CandidatosBombasWeb',
    'EjecucionesAgente','AprobacionesHITL','SimulacionesMonteCarlo','ResultadosMonteCarlo'
)
ORDER BY name;

SELECT TOP 100 id_bomba, codigo_bomba, modelo, potencia_hp, caudal_max_lmin,
       altura_max_mca, precio_ref_clp, fuente, activo
FROM dbo.Bombas
ORDER BY id_bomba;

SELECT TOP 100 * FROM dbo.CurvasBombas ORDER BY id_bomba, caudal_lmin;
SELECT TOP 100 * FROM dbo.CotizacionesBombasMercado ORDER BY fecha_consulta DESC;
SELECT TOP 100 * FROM dbo.CandidatosBombasWeb ORDER BY fecha_consulta DESC;
SELECT TOP 100 * FROM dbo.AprobacionesHITL ORDER BY fecha_solicitud DESC;
SELECT TOP 100 * FROM dbo.SimulacionesMonteCarlo ORDER BY fecha DESC;
GO
