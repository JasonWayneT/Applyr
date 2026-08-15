@AGENTS.md

## Claude Code

Claude Code loads this file at session start, not `AGENTS.md`. The import on the first line is the canonical Applyr instruction set. Do not paste `AGENTS.md` into this file.

On Windows, keep the import. Do not replace this file with a symlink.

Do not run `/init` in a way that regenerates a full copy of `AGENTS.md` here.

Stage 1 authoring still uses `authoring_prompt.md` only (digest plus packet). Do not load `data/agent_context_pack.md` into that author session.
