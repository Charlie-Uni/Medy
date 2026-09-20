\set ON_ERROR_STOP on
LOAD 'zhparser';
SELECT json_build_object(
  'postgresql', version(),
  'server_version', current_setting('server_version'),
  'server_version_num', current_setting('server_version_num'),
  'server_encoding', current_setting('server_encoding'),
  'lc_collate', (SELECT datcollate FROM pg_database WHERE datname = current_database()),
  'lc_ctype', (SELECT datctype FROM pg_database WHERE datname = current_database()),
  'extension', (SELECT row_to_json(e) FROM
      (SELECT extname, extversion FROM pg_extension WHERE extname = 'zhparser') e),
  'guc', (SELECT json_agg(g ORDER BY name) FROM
      (SELECT name, setting, boot_val, reset_val, source, context
       FROM pg_settings WHERE name LIKE 'zhparser.%') g),
  'token_types', (SELECT json_agg(t ORDER BY tokid) FROM ts_token_type('zhparser') t),
  'pos_mapping', (SELECT json_agg(m ORDER BY maptokentype, mapseqno) FROM
      (SELECT maptokentype, mapseqno, mapdict::regdictionary::text AS dictionary
       FROM pg_ts_config_map WHERE mapcfg = 'dec001_b'::regconfig) m),
  'custom_dictionary_rows', (SELECT count(*) FROM zhparser.zhprs_custom_word),
  'synthetic_results', (SELECT json_agg(s ORDER BY id) FROM
      (SELECT id, body,
          (SELECT json_agg(p ORDER BY ordinal) FROM ts_parse('zhparser', body)
            WITH ORDINALITY AS p(tokid, token, ordinal)) AS parser_tokens,
          to_tsvector('dec001_b', body)::text AS vector
       FROM synthetic_inputs) s),
  'synthetic_or_query', to_tsquery('dec001_b', 'synthetic | protocol')::text,
  'synthetic_ranked_ids', (SELECT json_agg(r ORDER BY score DESC, id) FROM
      (SELECT id, ts_rank_cd(vector, to_tsquery('dec001_b', 'synthetic | protocol'), 0) AS score
       FROM synthetic_vectors WHERE vector @@ to_tsquery('dec001_b', 'synthetic | protocol')) r)
);
