# Luma Atelier — PRD

## Original problem statement
Build & deploy "Luma Atelier", an Indonesian AI web app for content creators: AutoClip (YouTube reference + licensed master → up to 5 clips with hook/context/payoff/CTA, synced subtitles, subject crop, B-roll, music, ranked by quality, explain if fewer), AutoMotion (footage → cleaned pauses/audio/rhythm/framing + subtitles, typography, motion graphics, B-roll), Explainer (Ide Hari Ini from live ID+global trends w/ source, region, WIB time, reason, AI pick, evergreen fallback; or Topik Sendiri; styles clay/2D/3D/realistic; research, narration, storyboard, visuals, VO, subtitles, music, video). Shared: per-user projects/assets/versions/Brand Kit, persistent stage progress, editorial score 0–100 + reasons + timestamped suggestions, per-platform title/caption/hashtags, review (play, revise part, approve final), export MP4/SRT/metadata. Publishing to IG Reels, FB Reels, YouTube/Shorts, TikTok via official OAuth, only after approval; per-channel status, dedupe; config-needed state when no credentials; tokens server-side. Cinematic plum/champagne design, serif headings, CSS 3D with reduced motion.

## User choices
Email+password login (Emergent-managed Clerk) • AI image per scene animated (Nano Banana) • GPT (gpt-5.6-terra) for text • voices: warm (coral) & cinematic (onyx).

## Architecture
- FastAPI + MongoDB; Emergent Object Storage for all media; signed HMAC media URLs with Range support.
- In-process async worker (backend) with persisted stages in `projects`; resumes on restart. ffmpeg via imageio-ffmpeg (libx264, libass subtitles, zoompan, sidechain ducking); OpenCV face detection for crop; Whisper word timestamps; OpenAI TTS; procedural ambient music.
- Collections: projects, videos (plan + versions), assets, brand_kits, channels (tokens server-only), oauth_states, publications (unique dedupe_key), trends.
- Frontend React + Tailwind + shadcn; pages: Studio, Wizard per mode, Project/Review, Projects, Review queue, Brand Kit, Publikasi.

## Implemented (2026-11-23)
- All three modes end-to-end tested in preview (MP4 720x1280, SRT, metadata JSON); revision → v2 works; approve/unapprove.
- Trends from Google Trends RSS (ID + US) with LLM curation; evergreen fallback.
- OAuth connect + publish executors for YouTube, Instagram, Facebook, TikTok — NOT verified (no credentials); UI shows Kebutuhan Konfigurasi.
- Fixes after testing: visual-only explainer revision crash, FB/IG visibility respect, re-check approval at send time, forced safe content-type for uploads.

## Backlog
- P0: Social app credentials + platform approvals (Meta App Review, Google verification, TikTok audit); verify executors.
- P1: Pre-schedule time validation (no past dates), account-binding on schedule, worker claim for multi-instance, streaming uploads (memory), cache eviction, per-version metadata/plan snapshots, analyze-stage idempotency on retry, score validation.
- P2: Moving-subject crop tracking, YouTube transcript ingest (official captions API), grounded research with web sources, keyboard-accessible dropzone, multi-Page selector for Meta.
