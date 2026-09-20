\set ON_ERROR_STOP on
CREATE EXTENSION zhparser VERSION '2.3';
CREATE TEXT SEARCH CONFIGURATION dec001_b (PARSER = zhparser);
-- Fixed before smoke observations: retain every declared lexical POS except w.
ALTER TEXT SEARCH CONFIGURATION dec001_b ADD MAPPING
  FOR a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,x,y,z WITH simple;
CREATE TABLE synthetic_inputs (id text PRIMARY KEY, body text NOT NULL);
INSERT INTO synthetic_inputs VALUES
  ('mixed', '合成文档：不得自动提交；示例数值 12.5 mg，观察时间 48 h。Protocol SYN-2026-A uses 10 mg/kg.'),
  ('traditional', '合成紀錄：不得自動提交；觀察時間 48 小時。Synthetic report is not approved.'),
  ('ascii', 'Synthetic NOT approved protocol SYN-2026-A 12.5 mg/kg'),
  ('empty', '   ');
CREATE TABLE synthetic_vectors AS
  SELECT id, to_tsvector('dec001_b', body) AS vector FROM synthetic_inputs;
CREATE INDEX synthetic_vectors_gin ON synthetic_vectors USING gin (vector);
DO $$
BEGIN
  IF current_setting('server_version_num') <> '160015' THEN
    RAISE EXCEPTION 'expected PostgreSQL 16.15';
  END IF;
  IF (SELECT extversion FROM pg_extension WHERE extname = 'zhparser') <> '2.3' THEN
    RAISE EXCEPTION 'expected zhparser 2.3';
  END IF;
  IF EXISTS (SELECT FROM synthetic_vectors WHERE id <> 'empty' AND vector = ''::tsvector)
     OR EXISTS (SELECT FROM synthetic_vectors WHERE id = 'empty' AND vector <> ''::tsvector) THEN
    RAISE EXCEPTION 'synthetic empty/nonempty vector contract failed';
  END IF;
  IF NOT (SELECT vector @@ to_tsquery('dec001_b', 'synthetic | protocol')
          FROM synthetic_vectors WHERE id = 'ascii') THEN
    RAISE EXCEPTION 'synthetic OR lexical match failed';
  END IF;
  IF (SELECT count(*) FROM zhparser.zhprs_custom_word) <> 0 THEN
    RAISE EXCEPTION 'unexpected custom dictionary';
  END IF;
END $$;
