# ADR-0003: Cloudflare R2 for Object Storage

**Status:** proposed
**Date:** 2026-03-20
**Last updated:** 2026-03-20

**Chose:** Cloudflare R2 over AWS S3, Supabase Storage, local disk on Render
**Rationale:** Cloudflare R2 is S3-compatible (uses the same `boto3` SDK), charges zero egress fees, and offers 10 GB free storage with 1 million Class A operations/month on the free tier. For SOTA StatWorks, dataset files (.xlsx, .csv) and analysis output (.json) need durable storage that survives backend restarts. R2's zero-egress pricing is strategically superior to S3 for a product that repeatedly downloads user datasets for reanalysis. The S3-compatible API means the backend uses `boto3` — a well-documented, battle-tested SDK.

## Alternatives Considered

- **AWS S3:** Industry standard for object storage. However, S3 charges egress fees ($0.09/GB after free tier), requires an AWS account with billing setup, and the free tier is only 5 GB for 12 months. Rejected for egress cost and setup overhead during a hackathon.

- **Supabase Storage:** Already using Supabase for metadata — could consolidate. However, Supabase Storage has a 1 GB limit on the free tier (vs. R2's 10 GB), and file upload/download is slower compared to R2's edge network. Rejected for capacity constraints and performance.

- **Local disk on Render:** Render's free tier uses an ephemeral filesystem — files are lost on every deploy. Even paid tiers use ephemeral disk by default. Rejected because the entire motivation for adding storage is persistence.

## Consequences

- **Short-term:**
  - Backend adds `boto3` dependency (S3-compatible client).
  - New module `backend/storage/r2.py` with functions: `generate_presigned_upload_url()`, `generate_presigned_download_url()`, `get_file_stream()`.
  - R2 bucket structure: `users/{clerk_user_id}/datasets/{dataset_id}.csv` and `users/{clerk_user_id}/outputs/{analysis_id}.json`.
  - New env vars: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`.
  - Upload flow changes: frontend requests presigned URL → uploads directly to R2 → backend saves metadata to Supabase.
  - Build timeline increases by ~1–2 hours for R2 setup and presigned URL flow.

- **Long-term:**
  - Dataset files persist indefinitely (no process restart data loss).
  - Users can reload and re-analyze without re-uploading — "instant resume" UX.
  - Zero egress fees mean unlimited dataset downloads for reanalysis without cost scaling.
  - Presigned URLs mean the backend never handles raw file bytes for uploads — reduces memory pressure on Render's 512 MB free tier.
  - Security model: no public bucket access; all access via time-limited presigned URLs.
  - S3-compatible API means migration to AWS S3 or MinIO is trivial if needed post-hackathon.
