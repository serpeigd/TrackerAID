-- Esquema inicial de TrackerAID. Se aplicará vía Supabase (migraciones) en F4.
-- Diseñado para multiusuario público desde el día 1 (ver docs/adr/0003).
--
-- Punto crítico: `impressions.features_json` se congela en el momento en que
-- se muestra el documento al usuario. No se recalcula nunca a posteriori:
-- si se recalculara al reentrenar el reranker, se introduciría data leakage
-- (el modelo "vería" información que no tenía cuando se tomó la decisión).

create extension if not exists vector;
create extension if not exists pgcrypto;

-- Perfil de negocio del usuario: sector (CNAE), ámbito geográfico, tamaño.
create table profiles (
    user_id           uuid primary key references auth.users(id) on delete cascade,
    cnae              text[] not null default '{}',
    ambito            text not null default 'Comunitat Valenciana',
    tamano            text,                    -- autonomo | micro | pyme
    keywords          text[] not null default '{}',
    perfil_embedding  vector(1024),
    model_version     text,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

-- Registro de consentimiento RGPD. Se guarda de forma independiente del
-- perfil para poder demostrar cuándo y con qué texto se aceptó, aunque
-- el perfil cambie después.
create table consents (
    id                 uuid primary key default gen_random_uuid(),
    user_id            uuid not null references auth.users(id) on delete cascade,
    consent_ts         timestamptz not null default now(),
    texto_version      text not null,
    ip                 inet,
    double_optin_ts    timestamptz,
    unsubscribed_ts    timestamptz,
    source             text not null default 'landing'
);

-- Documentos ingeridos desde BDNS (una fila por convocatoria única).
create table documents (
    doc_id          bigint primary key,        -- id de BDNS, no generado
    source          text not null default 'bdns',
    source_url      text,
    published_at    date,
    raw_hash        text not null,             -- hash del contenido crudo, para detectar cambios
    title           text not null,
    body            text,
    ingested_at     timestamptz not null default now()
);

-- Campos extraídos (reglas y/o LLM) de cada documento.
create table doc_fields (
    doc_id             bigint primary key references documents(doc_id) on delete cascade,
    importe            numeric,
    deadline           date,
    ambito             text,
    cnae               text[],
    beneficiarios      text,
    extractor_version  text not null,
    confidence         numeric,
    cost_tokens        integer,
    extracted_at       timestamptz not null default now()
);

create table doc_embeddings (
    doc_id        bigint not null references documents(doc_id) on delete cascade,
    model_version text not null,
    embedding     vector(1024) not null,
    primary key (doc_id, model_version)
);

create table digests (
    digest_id          uuid primary key default gen_random_uuid(),
    user_id            uuid not null references auth.users(id) on delete cascade,
    sent_at            timestamptz not null default now(),
    n_items            integer not null default 0,
    provider_message_id text
);

-- El activo crítico del proyecto: qué se le mostró a quién, en qué
-- posición, con qué score y con qué versión de modelo. Sin esto no hay
-- reranker posible (F6).
create table impressions (
    impression_id  uuid primary key default gen_random_uuid(),
    digest_id      uuid not null references digests(digest_id) on delete cascade,
    user_id        uuid not null references auth.users(id) on delete cascade,
    doc_id         bigint not null references documents(doc_id),
    position       integer not null,
    score          numeric not null,
    model_version  text not null,
    features_json  jsonb not null,
    shown_at       timestamptz not null default now()
);

create table feedback (
    id             uuid primary key default gen_random_uuid(),
    impression_id  uuid not null references impressions(impression_id) on delete cascade,
    label          text not null check (label in ('up', 'down', 'saved', 'clicked')),
    ts             timestamptz not null default now()
);

-- Gold set etiquetado a mano para evaluar retrieval (F1). Independiente
-- del feedback real de usuarios, que se usa para F6.
create table gold_labels (
    id          uuid primary key default gen_random_uuid(),
    profile_id  uuid references profiles(user_id),
    doc_id      bigint not null references documents(doc_id),
    relevance   smallint not null check (relevance in (0, 1, 2)),
    annotator   text not null,
    ts          timestamptz not null default now()
);

create table eval_runs (
    run_id          uuid primary key default gen_random_uuid(),
    dataset_version text not null,
    model_version   text not null,
    metric          text not null,   -- recall@20 | ndcg@10 | precision@5 | mrr
    value           numeric not null,
    ts              timestamptz not null default now()
);

create index idx_impressions_user on impressions(user_id);
create index idx_impressions_doc on impressions(doc_id);
create index idx_doc_embeddings_doc on doc_embeddings(doc_id);
create index idx_documents_published_at on documents(published_at);

-- Row Level Security: cada usuario solo ve sus propios datos.
alter table profiles enable row level security;
alter table consents enable row level security;
alter table digests enable row level security;
alter table impressions enable row level security;
alter table feedback enable row level security;

create policy "own profile" on profiles for all using (auth.uid() = user_id);
create policy "own consents" on consents for select using (auth.uid() = user_id);
create policy "own digests" on digests for select using (auth.uid() = user_id);
create policy "own impressions" on impressions for select using (auth.uid() = user_id);
create policy "own feedback" on feedback for all using (
    auth.uid() = (select user_id from impressions where impressions.impression_id = feedback.impression_id)
);
