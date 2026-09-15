-- atos_organizacionais.sql
-- Procura, entre os atos lançados hoje no Radar RJ, os que trazem um organograma
-- ("1. Gabinete do Secretário", "1.1 - Chefia de Gabinete" e variações) e exporta
-- id|dataPubli|secao|texto em CSV.
--
-- Uso:
--   psql "$RADAR_DB" -X -q -v ON_ERROR_STOP=1 -f atos_organizacionais.sql \
--        > atos_organizacionais_$(date +%F).csv
--
-- Requer (uma vez, feito por um admin):  CREATE EXTENSION IF NOT EXISTS unaccent;

COPY (
    WITH atos_do_dia AS (
        SELECT
            a.id,
            a."dataPubli",
            a.secao,
            a.texto,
            -- sem acento, minúsculo e com espaços (inclusive &nbsp;) reduzidos a um só
            lower(unaccent(regexp_replace(a.texto, '[[:space:]\u00a0]+', ' ', 'g'))) AS texto_busca
        FROM radarrj.ato AS a                    -- ajuste schema.tabela
        WHERE a."createdAt" >= current_date      -- lançados hoje
          AND a."createdAt" <  current_date + 1
    )
    SELECT id, "dataPubli", secao, texto
    FROM atos_do_dia
    WHERE texto_busca ~ (
          '(^|[^0-9.])1'                         -- item "1" (e não o fim de "200.101")
       || '( *[.)–-][ .)–-]*'                    -- "1." / "1 -" / "1 . -" / "1)"
       || '| *\. *1[ .)–-]*)'                    -- ou "1.1" / "1.1." / "1 . 1 -"
       || '(gabinete d[aoe]s? secretari[ao]'     -- Gabinete do/da Secretário/a
       || '|chefia de gabinete)'                 -- Chefia de Gabinete (cobre "1. Presidência  1.1. Chefia...")
    )
    ORDER BY "dataPubli", id
) TO STDOUT WITH (FORMAT csv, DELIMITER '|', HEADER);
