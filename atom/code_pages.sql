-- Enable the pgvector extension
create extension if not exists vector;

-- Create the documentation chunks table
create table code_pages (
    id bigserial primary key,
    chunk_idx integer not null,
    type_name varchar not null,
    summary varchar not null,
    content text not null,  -- Added content column
    metadata jsonb not null default '{}'::jsonb,  -- Added metadata column
    embedding vector(1536),  -- OpenAI embeddings are 1536 dimensions
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    
    -- Add a unique constraint to prevent duplicate chunks for the same URL
    unique(type_name, chunk_idx)
);

-- Create an index for better vector similarity search performance
create index on code_pages using ivfflat (embedding vector_cosine_ops);

-- Create an index on metadata for faster filtering
create index idx_code_pages_metadata on code_pages using gin (metadata);

-- Create a function to search for documentation chunks
create function match_code_pages (
  query_embedding vector(1536),
  match_count int default 10,
  filter jsonb DEFAULT '{}'::jsonb
) returns table (
  id bigint,
  chunk_idx integer,
  type_name varchar,
  summary varchar,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
#variable_conflict use_column
begin
  return query
  select
    id,
    chunk_number,
    type_name,
    summary,
    content,
    metadata,
    1 - (code_pages.embedding <=> query_embedding) as similarity
  from code_pages
  where metadata @> filter
  order by code_pages.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Everything above will work for any PostgreSQL database. The below commands are for Supabase security

-- Enable RLS on the table
alter table code_pages enable row level security;

-- Create a policy that allows anyone to read
create policy "Allow public read access"
  on code_pages
  for select
  to public
  using (true);
