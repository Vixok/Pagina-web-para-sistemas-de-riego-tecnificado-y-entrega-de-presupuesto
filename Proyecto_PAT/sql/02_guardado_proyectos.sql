USE PAT_RIEGO;
GO

SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'dbo.Proyectos', N'U') IS NULL
    THROW 50001, 'No existe dbo.Proyectos. Ejecute primero el esquema base y la migracion PAT-V2.', 1;
GO

IF COL_LENGTH(N'dbo.Proyectos', N'datos_json') IS NULL
    ALTER TABLE dbo.Proyectos ADD datos_json NVARCHAR(MAX) NULL;
GO

SELECT
    OBJECT_NAME(object_id) AS tabla,
    name AS columna,
    TYPE_NAME(system_type_id) AS tipo
FROM sys.columns
WHERE object_id = OBJECT_ID(N'dbo.Proyectos')
  AND name = N'datos_json';
GO
