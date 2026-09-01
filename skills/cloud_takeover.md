# skill: cloud_takeover
title: Cloud & BaaS Takeover (Supabase / Firebase / Metadata)
when: supabase,firebase,aws,cloud,anon_key,bucket,ssrf,metadata,baas,s3,r2

## OPERATING PRINCIPLE
Cloud apps leak their skeleton in the frontend: anon keys in bundles,
supabase refs in JS, bucket URLs in config. The BaaS pattern is our
signature move — the anon key is not a vulnerability, the RLS that trusts
it is.

## SUPABASE CHAIN (our proven siege line)
1. supabase_exfil(anon_key, base_url) — PREFERRED first strike: full table
   dump through the REST grammar. More reliable than full assault.
2. If RLS blocks: auth_signup_probe(base, email_domain) — mint a real
   session; service role often trusts any authenticated identity.
3. auth_metadata_poison(base, token, fields={role:admin,...}) — write
   privileged-looking fields into user_metadata; apps that read trust from
   metadata get owned by their own mirror.
4. realtime_tap(anon_key, tables=[...]) — live row capture on the tables
   the exfil found; sometimes rows stream that REST filters out.
5. supabase_full_assault as the exhaustive sweep when time is cheap.

## GENERIC CLOUD CHAIN
1. js_mine_site — harvest: supabase refs, firebase configs, AWS keys
   (AKIA...), GCP tokens, R2/S3 bucket URLs. secret_scan the dumps.
2. Buckets found → data_extract on bucket listing URLs (public read often
   open even when the console says private).
3. SSRF surface (pdf generators, importers, webhooks) → ssrf_probe against
   cloud metadata: 169.254.169.254/latest/meta-data/ (EC2),
   metadata.google.internal/computeMetadata/v1/ (needs Metadata-Flavor hdr),
   169.254.169.254/metadata/instance (Azure). IMDSv2 requires PUT with
   X-aws-ec2-metadata-token-ttl-seconds — try both.
4. Keys from metadata → they ARE the takeover: scope them with the cloud
   CLIs conceptually, enumerate roles, note the blast radius in the report.
5. Firebase: /.well-known/firebase-rules or /rest?auth=... patterns;
   open rules = data_dump_paginated on the REST grammar.

## EXTRACTION LAW
Every key you find must be TESTED (data_extract with it as Authorization
or X-Api-Key on every discovered endpoint) and every tested key gets a
verdict in the report: working / scoped / dead.

## FAILURE MODES
- RLS tight on REST: try RPC endpoints (`/rest/v1/rpc/<fn>`) — functions
  often run with elevated roles and weaker input validation.
- Metadata 403: IMDSv2 — look for SSRF that can issue the PUT token first.
- Anon key rotates: re-harvest from JS after deploys (deploy_watch diff).
