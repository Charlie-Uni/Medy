\set ON_ERROR_STOP on
CREATE EXTENSION vector;
CREATE EXTENSION pg_search;
DO $$
BEGIN
  IF (SELECT extversion FROM pg_extension WHERE extname = 'pg_search') <> '0.25.9' THEN
    RAISE EXCEPTION 'unexpected pg_search version';
  END IF;
  IF current_setting('server_version_num') <> '160015' THEN
    RAISE EXCEPTION 'unexpected PostgreSQL version';
  END IF;
END $$;

SELECT jsonb_build_object(
  'kind', 'runtime',
  'postgresql', version(),
  'extension_version', (SELECT extversion FROM pg_extension WHERE extname = 'pg_search'),
  'vector_extension_version', (SELECT extversion FROM pg_extension WHERE extname = 'vector'),
  'version_info', (SELECT row_to_json(v) FROM paradedb.version_info() AS v),
  'shared_preload_libraries', current_setting('shared_preload_libraries'),
  'max_parallel_workers', current_setting('max_parallel_workers'),
  'shared_buffers', current_setting('shared_buffers')
);

-- One predeclared Jieba configuration. Omitted optional filters remain disabled;
-- no custom dictionary, stemming, stopwords, length filter or Chinese conversion.
SELECT jsonb_build_object(
  'kind', 'tokenizer',
  'synthetic_input', '研究报告 Alpha 0.5 mg PROT-2042-123 醫師',
  'tokens', '研究报告 Alpha 0.5 mg PROT-2042-123 醫師'::pdb.jieba(
    'lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false'
  )::text[]
);

CREATE TABLE candidate_c_smoke (id bigint PRIMARY KEY, body text NOT NULL);
INSERT INTO candidate_c_smoke VALUES
  (1, '研究报告 alpha'),
  (2, '研究方案 beta'),
  (3, 'ordinary gamma');
CREATE INDEX candidate_c_smoke_idx ON candidate_c_smoke
USING bm25 (id, (body::pdb.jieba(
  'lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false'
))) WITH (key_field = 'id');

SELECT jsonb_build_object(
  'kind', 'index_schema', 'fields', (SELECT jsonb_agg(to_jsonb(s) ORDER BY name)
                                  FROM paradedb.schema('candidate_c_smoke_idx') AS s)
);

DO $$
DECLARE
  ids bigint[];
BEGIN
  SELECT array_agg(id ORDER BY id) INTO ids FROM candidate_c_smoke
  WHERE (body::pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')) ||| '研究';
  IF ids IS DISTINCT FROM ARRAY[1, 2]::bigint[] THEN
    RAISE EXCEPTION 'synthetic Chinese retrieval mismatch';
  END IF;
  SELECT array_agg(id ORDER BY id) INTO ids FROM candidate_c_smoke
  WHERE (body::pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')) ||| 'alpha';
  IF ids IS DISTINCT FROM ARRAY[1]::bigint[] THEN
    RAISE EXCEPTION 'synthetic English retrieval mismatch';
  END IF;
  IF EXISTS (SELECT 1 FROM candidate_c_smoke
     WHERE (body::pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')) ||| 'neverpresent') THEN
    RAISE EXCEPTION 'synthetic zero-match mismatch';
  END IF;
END $$;

-- Record multiword OR behavior; default Jieba preserves whitespace tokens.
-- This is a diagnostic, not the production adapter's OR/count acceptance test.
SELECT jsonb_build_object(
  'kind', 'multiword_or_diagnostic',
  'query', 'alpha gamma',
  'query_tokens', 'alpha gamma'::pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')::text[],
  'matching_ids', (SELECT array_agg(id ORDER BY id) FROM candidate_c_smoke
    WHERE (body::pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')) ||| 'alpha gamma')
);

SELECT jsonb_build_object('kind', 'bm25_results', 'rows', jsonb_agg(to_jsonb(r) ORDER BY score DESC, id))
FROM (
  SELECT id, paradedb.score(id) AS score FROM candidate_c_smoke
  WHERE (body::pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')) ||| '研究'
  ORDER BY score DESC, id ASC LIMIT 20
) AS r;

EXPLAIN (FORMAT JSON, COSTS OFF)
SELECT id, paradedb.score(id) AS score FROM candidate_c_smoke
WHERE (body::pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')) ||| '研究'
ORDER BY score DESC, id ASC LIMIT 20;
