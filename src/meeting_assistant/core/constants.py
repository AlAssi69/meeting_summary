"""Shared constants (DRY)."""

from __future__ import annotations

from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"


class MessageSystemKind(str, Enum):
    """Severity for persisted system rows (QML maps to banner colors)."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AssistantContentKind(str, Enum):
    """Distinguishes assistant bubbles (``assistant_kind``; transcript may fall back to ``file_path``)."""

    TRANSCRIPT = "transcript"
    SUMMARY = "summary"
    SPEAKER_MAP = "speaker_map"


# Supported audio extensions for drop / file picker
AUDIO_EXTENSIONS: frozenset[str] = frozenset({".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac"})

# Global prompts (LLM system vs Whisper initial_prompt bias).
SETTINGS_KEY_GLOBAL_LLM_SYSTEM: str = "global_llm_system_prompt"
SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT: str = "global_whisper_context"
SETTINGS_KEY_MEETING_OUTPUT_ROOT: str = "meeting_output_root"
SETTINGS_KEY_UI_LANGUAGE: str = "ui_language"

# Hugging Face token for WhisperX (real STT path); Settings preferred over env when non-empty.
SETTINGS_KEY_HF_ACCESS_TOKEN: str = "hf_access_token"

# Removed from application logic; stripped from SQLite on startup if still present.
SETTINGS_DEPRECATED_SQLITE_KEYS: frozenset[str] = frozenset(
    {
        "global_default_prompt",
        "prompt_bundle_v2_applied",
    }
)

# UI locale code persisted in app_settings: "ar" | "en"
DEFAULT_UI_LANGUAGE: str = "ar"

DEFAULT_SUMMARY_PROMPT: str = (
    "أنت مساعد ذكي خبير في إدارة الأعمال وتلخيص الاجتماعات المهنية، التقنية، والإدارية. "
    "مهمتك هي تحليل النص المفرغ من الاجتماع وتقديم ملخص شامل ومنظم بدقة باللغة العربية الفصحى.\n\n"
    "يجب أن يحتوي الملخص دائماً على الأقسام الأربعة التالية بالترتيب:\n"
    "1. **الملخص التنفيذي:** فقرة موجزة تلخص الغرض الرئيسي من الاجتماع والنتيجة النهائية.\n"
    "2. **النقاط الرئيسية:** قائمة نقطية تفصل أهم المواضيع التقنية والإدارية التي تمت مناقشتها.\n"
    "3. **القرارات المتخذة:** قائمة واضحة وحاسمة بالقرارات التي تم اعتمادها خلال الجلسة.\n"
    "4. **خطوات العمل (Action Items):** المهام المطلوبة، مع تحديد الشخص المسؤول عن كل مهمة والموعد النهائي "
    "(إن تم ذكره).\n\n"
    "التزم بالدقة، والموضوعية، والاحترافية. تجاهل الأحاديث الجانبية أو غير الرسمية."
)

DEFAULT_WHISPER_CONTEXT: str = (
    "شركة راشيس، الدكتور يزن، ماجد، عبد العزيز. هندسة البرمجيات، نماذج لغوية، ذكاء اصطناعي، "
    "خوارزميات التحكم، إدارة المشاريع، ميزانية، تقرير فني، بايثون، سي شارب، أتمتة، مراجعة الكود، بيئة العمل. "
    "Where technical terms should stay in Latin letters: Kalman filter, REST API, Docker, Git, LLM, GPU."
)

# Pre-filled in the chat UI for each new recording (user may edit or clear).
DEFAULT_RECORDING_LLM_INSTRUCTIONS: str = (
    "ركز بشكل خاص على النقاط المتعلقة بتقييم أداء النماذج اللغوية المحلية (LLMs) والجدول الزمني المقترح للنشر. "
    "يرجى إبراز أي تحديات تقنية تم ذكرها بخصوص الذاكرة أو سرعة الاستجابة، وتجاهل النقاش المبدئي حول الإجازات."
)

DEFAULT_RECORDING_WHISPER_CONTEXT: str = (
    "ماتلاب، محاكاة، أموال، MATLAB، Monte Carlo، Kalman filter، REST"
)
