CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS users(id serial PRIMARY KEY, name text, role text); -- lead | outgoing | incoming
CREATE TABLE IF NOT EXISTS sources(id serial PRIMARY KEY, title text, kind text, content text, author text,
  authored_at timestamptz DEFAULT now(), allowed_roles text[] NOT NULL DEFAULT '{lead,outgoing,incoming}', embedding vector(64));
CREATE TABLE IF NOT EXISTS claims(id serial PRIMARY KEY, kind text, text text, owner text, topic text,
  status text, source_id int REFERENCES sources(id), snippet text, review text DEFAULT 'pending',
  version int DEFAULT 1, happened_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS claim_versions(id serial PRIMARY KEY, claim_id int REFERENCES claims(id), version int,
  text text, owner text, status text, review text, editor text, at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS gaps(id serial PRIMARY KEY, claim_id int REFERENCES claims(id), question text, answered bool DEFAULT false);
CREATE TABLE IF NOT EXISTS audit(id serial PRIMARY KEY, actor text, action text, target text, at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS acks(id serial PRIMARY KEY, user_name text, at timestamptz DEFAULT now());
