# Contributing

Issues and pull requests are welcome.

**Last documentation alignment audit:** 2026-06-29 (env reference gap fixes: added `MEETING_ASSISTANT_OFFLINE_BUNDLE` and `MEETING_ASSISTANT_WHISPER_API_URL` to README; indexed `docs/TROUBLESHOOTING_NLTK_PUNKT_TAB.md` across the doc set).

---

## Development setup

From the repository root:

```powershell
# Windows PowerShell
$env:PYTHONPATH = "$PWD\src"
pytest
```

```bash
# macOS / Linux
PYTHONPATH=src pytest
```

Optional: `pip install '.[dev]'` then `ruff check src tests`.

---

## Documentation sync rules

Code is the source of truth. When you change behavior, keep prose docs aligned.

| When you change… | Also update… |
|------------------|--------------|
| Env var name, default, or semantics | [`src/meeting_assistant/config.py`](src/meeting_assistant/config.py) (or [`src/meeting_assistant/services/output_paths.py`](src/meeting_assistant/services/output_paths.py) for `MEETING_ASSISTANT_OUTPUT_ROOT`), [README.md](README.md) env tables, [`.env.example`](.env.example) if commonly used |
| Settings key or default prompt text | [`src/meeting_assistant/core/constants.py`](src/meeting_assistant/core/constants.py), README *constants.py* summary, [docs/SRS.md](docs/SRS.md) if user-visible behavior changes |
| DB schema or migrations | [`src/meeting_assistant/adapters/sqlite_session_repository.py`](src/meeting_assistant/adapters/sqlite_session_repository.py), SRS §2.4, [Feature SRS](docs/Feature%20SRS%20-%20Speaker%20Diarization%20and%20Alignment.md) if speaker-related |
| Pipeline order or worker contracts | README *Current pipeline*, SRS §3.5, Feature SRS if diarization, [docs/PROJECT_DESCRIPTION.md](docs/PROJECT_DESCRIPTION.md) if the high-level story changes |
| Install paths or launchers (`run.ps1`, `run.bat`) | README *Install* / *How to run*, [docs/INSTALLATION_AR.md](docs/INSTALLATION_AR.md) |
| Offline USB bundle (`packaging/offline/`) | [packaging/offline/README.md](packaging/offline/README.md), [docs/OFFLINE_DOCKER_HANDOFF.md](docs/OFFLINE_DOCKER_HANDOFF.md), [docs/INSTALLATION_AR.md](docs/INSTALLATION_AR.md) § Path A, README § Offline USB bundle, [docs/TROUBLESHOOTING_NLTK_PUNKT_TAB.md](docs/TROUBLESHOOTING_NLTK_PUNKT_TAB.md) if NLTK/alignment seeding changes |
| User-facing Arabic install steps | [docs/INSTALLATION_AR.md](docs/INSTALLATION_AR.md) |

**Doc set in scope:**

- [README.md](README.md) — operator/dev runbook and full env reference
- [docs/SRS.md](docs/SRS.md) — product intent and architecture
- [docs/PROJECT_DESCRIPTION.md](docs/PROJECT_DESCRIPTION.md) — consultation brief
- [docs/INSTALLATION_AR.md](docs/INSTALLATION_AR.md) — Arabic Windows install/migration
- [docs/OFFLINE_DOCKER_HANDOFF.md](docs/OFFLINE_DOCKER_HANDOFF.md) — air-gapped USB bundle (Path A)
- [packaging/offline/README.md](packaging/offline/README.md) — offline packaging implementation and scripts
- [docs/Feature SRS - Speaker Diarization and Alignment.md](docs/Feature%20SRS%20-%20Speaker%20Diarization%20and%20Alignment.md) — diarization addendum
- [docs/TROUBLESHOOTING_NLTK_PUNKT_TAB.md](docs/TROUBLESHOOTING_NLTK_PUNKT_TAB.md) — offline-bundle NLTK `punkt_tab` alignment fix
- [`.env.example`](.env.example) — commented env template

---

## Pull request checklist

Copy into your PR description when behavior or configuration changes:

- [ ] If behavior changed: updated [docs/SRS.md](docs/SRS.md) (intent) and [README.md](README.md) (defaults/runbook)
- [ ] If env/settings changed: `config.py` / `constants.py` / `output_paths.py` + README + `.env.example` when applicable
- [ ] If schema changed: SRS + Feature SRS (speakers)
- [ ] If high-level product story changed: [docs/PROJECT_DESCRIPTION.md](docs/PROJECT_DESCRIPTION.md)
- [ ] If Windows/Arabic install or USB bundle affected: [docs/INSTALLATION_AR.md](docs/INSTALLATION_AR.md) and/or [docs/OFFLINE_DOCKER_HANDOFF.md](docs/OFFLINE_DOCKER_HANDOFF.md)
- [ ] Project tree / doc index lists still accurate
- [ ] `pytest` passes (`PYTHONPATH=src`)

---

## Periodic re-audit

Before a release or roughly quarterly, re-check:

1. Every `MEETING_ASSISTANT_*` in code appears in README with correct default; common vars appear in `.env.example`.
2. SRS §2.4 schema matches `sqlite_session_repository.py` (including `session_speakers`).
3. Cross-links between all docs in the table above still resolve.
4. README and PROJECT_DESCRIPTION project trees list all `docs/` files, `packaging/offline/`, and launchers.

Update the **Last documentation alignment audit** line at the top of this file when done.
