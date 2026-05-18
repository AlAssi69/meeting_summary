from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from meeting_assistant.core.constants import (
    DEFAULT_SUMMARY_PROMPT,
    DEFAULT_UI_LANGUAGE,
    DEFAULT_WHISPER_CONTEXT,
    SETTINGS_KEY_GLOBAL_LLM_SYSTEM,
    SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT,
    SETTINGS_KEY_HF_ACCESS_TOKEN,
    SETTINGS_KEY_MEETING_OUTPUT_ROOT,
    SETTINGS_KEY_UI_LANGUAGE,
    MessageRole,
)
from meeting_assistant.core.models import Message, Session
from meeting_assistant.ports.session_repository import SessionRepository


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class InMemorySessionRepository(SessionRepository):
    """Volatile store for mock / UI-only runs."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._messages: dict[str, list[Message]] = {}
        self._session_speakers: dict[str, dict[str, str]] = {}
        self._settings: dict[str, str] = {
            SETTINGS_KEY_GLOBAL_LLM_SYSTEM: DEFAULT_SUMMARY_PROMPT,
            SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT: DEFAULT_WHISPER_CONTEXT,
            SETTINGS_KEY_MEETING_OUTPUT_ROOT: "",
            SETTINGS_KEY_UI_LANGUAGE: DEFAULT_UI_LANGUAGE,
            SETTINGS_KEY_HF_ACCESS_TOKEN: "",
        }

    def list_sessions(self) -> list[Session]:
        return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    def create_session(self, title: str) -> Session:
        from meeting_assistant.services.session_artifact_folder import allocate_unique_session_slug

        sid = str(uuid.uuid4())
        created = _iso_now()
        slug = allocate_unique_session_slug(self, title)
        s = Session(id=sid, title=title, created_at=created, artifacts_slug=slug)
        self._sessions[sid] = s
        self._messages[sid] = []
        return s

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def set_session_title(self, session_id: str, title: str) -> None:
        if session_id not in self._sessions:
            return
        old = self._sessions[session_id]
        self._sessions[session_id] = Session(
            id=old.id,
            title=title,
            created_at=old.created_at,
            artifacts_slug=old.artifacts_slug,
        )

    def set_session_artifacts_slug(self, session_id: str, slug: str) -> None:
        if session_id not in self._sessions:
            return
        old = self._sessions[session_id]
        self._sessions[session_id] = Session(
            id=old.id,
            title=old.title,
            created_at=old.created_at,
            artifacts_slug=slug,
        )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str | None,
        file_path: str | None,
        *,
        system_kind: str | None = None,
        recording_llm_instructions: str | None = None,
        recording_whisper_context: str | None = None,
        assistant_kind: str | None = None,
    ) -> Message:
        if session_id not in self._sessions:
            raise KeyError(session_id)
        mid = str(uuid.uuid4())
        m = Message(
            id=mid,
            session_id=session_id,
            role=role,
            content=content,
            file_path=file_path,
            created_at=_iso_now(),
            system_kind=system_kind,
            recording_llm_instructions=recording_llm_instructions,
            recording_whisper_context=recording_whisper_context,
            assistant_kind=assistant_kind,
        )
        self._messages.setdefault(session_id, []).append(m)
        return m

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._messages.pop(session_id, None)
        self._session_speakers.pop(session_id, None)

    def list_messages(self, session_id: str) -> list[Message]:
        return list(self._messages.get(session_id, []))

    def delete_messages_after_user_with_file(self, session_id: str, file_path: str) -> None:
        try:
            target = str(Path(file_path).resolve())
        except OSError:
            target = file_path
        bucket = self._messages.get(session_id)
        if not bucket:
            return
        msgs = list(bucket)
        anchor: int | None = None
        for i in range(len(msgs) - 1, -1, -1):
            m = msgs[i]
            if m.role != MessageRole.USER.value or not m.file_path:
                continue
            try:
                if str(Path(m.file_path).resolve()) == target:
                    anchor = i
                    break
            except OSError:
                if m.file_path == file_path:
                    anchor = i
                    break
        if anchor is None:
            return
        keep: list[Message] = msgs[: anchor + 1]
        for j in range(anchor + 1, len(msgs)):
            if msgs[j].role == MessageRole.USER.value:
                keep.extend(msgs[j:])
                break
        if len(keep) == len(msgs):
            return
        self._messages[session_id] = keep

    def get_global_llm_system(self) -> str:
        return self._settings.get(SETTINGS_KEY_GLOBAL_LLM_SYSTEM, DEFAULT_SUMMARY_PROMPT)

    def set_global_llm_system(self, value: str) -> None:
        self._settings[SETTINGS_KEY_GLOBAL_LLM_SYSTEM] = value

    def get_global_whisper_context(self) -> str:
        return self._settings.get(SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT, DEFAULT_WHISPER_CONTEXT)

    def set_global_whisper_context(self, value: str) -> None:
        self._settings[SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT] = value

    def get_meeting_output_root(self) -> str:
        return self._settings.get(SETTINGS_KEY_MEETING_OUTPUT_ROOT, "")

    def set_meeting_output_root(self, value: str) -> None:
        self._settings[SETTINGS_KEY_MEETING_OUTPUT_ROOT] = value.strip()

    def get_ui_language(self) -> str:
        v = (self._settings.get(SETTINGS_KEY_UI_LANGUAGE) or "").strip().lower()
        if v in ("ar", "en"):
            return v
        return DEFAULT_UI_LANGUAGE

    def set_ui_language(self, value: str) -> None:
        raw = (value or "").strip().lower()
        if raw not in ("ar", "en"):
            raw = DEFAULT_UI_LANGUAGE
        self._settings[SETTINGS_KEY_UI_LANGUAGE] = raw

    def get_hf_access_token(self) -> str:
        return (self._settings.get(SETTINGS_KEY_HF_ACCESS_TOKEN) or "").strip()

    def set_hf_access_token(self, value: str) -> None:
        self._settings[SETTINGS_KEY_HF_ACCESS_TOKEN] = value.strip()

    def list_session_speakers(self, session_id: str) -> list[tuple[str, str]]:
        d = self._session_speakers.get(session_id) or {}
        return sorted(d.items(), key=lambda kv: kv[0])

    def replace_session_speakers(self, session_id: str, mapping: dict[str, str]) -> None:
        out: dict[str, str] = {}
        for key, name in mapping.items():
            k = (key or "").strip()
            if not k:
                continue
            n = (name or "").strip() or k
            out[k] = n
        self._session_speakers[session_id] = out

    def update_assistant_message_content(
        self, session_id: str, message_id: str, content: str
    ) -> None:
        bucket = self._messages.get(session_id)
        if not bucket:
            return
        for i, m in enumerate(bucket):
            if m.id != message_id or m.role != MessageRole.ASSISTANT.value:
                continue
            bucket[i] = Message(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=content,
                file_path=m.file_path,
                created_at=m.created_at,
                system_kind=m.system_kind,
                recording_llm_instructions=m.recording_llm_instructions,
                recording_whisper_context=m.recording_whisper_context,
                assistant_kind=m.assistant_kind,
            )
            break

    def delete_message(self, session_id: str, message_id: str) -> None:
        bucket = self._messages.get(session_id)
        if not bucket:
            return
        self._messages[session_id] = [m for m in bucket if m.id != message_id]
