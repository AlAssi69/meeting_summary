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

# Speaker diarization (pyannote via WhisperX); persisted as "1" / "0" in app_settings.
SETTINGS_KEY_SPEAKER_DIARIZATION_ENABLED: str = "speaker_diarization_enabled"
DEFAULT_SPEAKER_DIARIZATION_ENABLED: bool = False

# Removed from application logic; stripped from SQLite on startup if still present.
SETTINGS_DEPRECATED_SQLITE_KEYS: frozenset[str] = frozenset(
    {
        "global_default_prompt",
        "prompt_bundle_v2_applied",
    }
)

# UI locale code persisted in app_settings: "ar" | "en"
DEFAULT_UI_LANGUAGE: str = "ar"

DEFAULT_SUMMARY_PROMPT: str = """أنت مساعد ذكي ومحلل خبير في إدارة الاجتماعات الهندسية والتقنية. سأقدم لك نصاً تفريغياً لاجتماع (Transcript) مقسم حسب المتحدثين والتسلسل الزمني.

مهمتك هي قراءة النص بعناية وتقديم ملخص شامل، دقيق، ومنظم باللغة العربية الفصحى. يجب أن تكون المخرجات مُنسقة بالكامل باستخدام تنسيق (Markdown) لتوضيح العناوين، القوائم، والنصوص البارزة.

يجب أن تلتزم بالهيكل التالي في مخرجاتك:

## 1. نبذة عامة (Executive Summary)
فقرة قصيرة ومركزة تلخص الهدف الأساسي من الاجتماع والنتيجة النهائية التي تم التوصل إليها.

## 2. المشاريع والمواضيع المطروحة (Projects & Topics)
قائمة نقطية تستعرض:
- المشاريع الحالية أو المستقبلية التي تمت مناقشتها.
- المواضيع الهندسية أو الفنية الأساسية.
- الأفكار الجديدة (Ideas) أو الحلول المقترحة خلال الجلسة.

## 3. تفصيل المتحدثين (Speaker Breakdown)
لكل متحدث تم ذكره في النص، قدم ملخصاً بالشكل التالي:
- **[اسم المتحدث]**:
  - الأفكار أو التحديثات التي طرحها.
  - موقفه أو رأيه الفني حيال المواضيع المطروحة.

## 4. القرارات والخطوات المستقبلية (Action Items & Future Tasks)
قائمة واضحة ومحددة تشمل:
- **القرارات المعتمدة**: ما تم الاتفاق عليه نهائياً.
- **المهام الموكلة (Action Items)**: المهام المطلوبة مع تحديد الشخص المسؤول عن تنفيذها (إن وُجد).
- **الخطوات المستقبلية (Future Tasks)**: التوجهات أو التحضيرات المطلوبة للاجتماعات أو المراحل القادمة من المشروع.

قواعد صارمة يجب الالتزام بها:
- المخرجات يجب أن تكون باللغة العربية الفصحى السليمة والاحترافية.
- الحفاظ على المصطلحات التقنية والهندسية: إذا واجهت مصطلحات إنجليزية داخل النص (مثل Control Theory, Kalman Filter, LQR, State Space)، اكتبها باللغة الإنجليزية كما هي تماماً. يُمنع منعاً باتاً تعريب هذه المصطلحات أو كتابتها بحروف عربية.
- الدقة والموضوعية: استخرج الملخص من النص المرفق فقط. يُمنع تأليف أو إضافة أي معلومات، تواريخ، أو أحداث غير موجودة في النص.
- إذا كانت هناك أجزاء غير واضحة أو كلمات غير مفهومة في النص، تجاوزها وركز على النقاط المفهومة فقط."""

DEFAULT_WHISPER_CONTEXT: str = ""

# Pre-filled in the chat UI for each new recording (user may edit or clear).
DEFAULT_RECORDING_LLM_INSTRUCTIONS: str = (
    "ركز بشكل خاص على النقاط المتعلقة بتقييم أداء النماذج اللغوية المحلية (LLMs) والجدول الزمني المقترح للنشر. "
    "يرجى إبراز أي تحديات تقنية تم ذكرها بخصوص الذاكرة أو سرعة الاستجابة، وتجاهل النقاش المبدئي حول الإجازات."
)

DEFAULT_RECORDING_WHISPER_CONTEXT: str = ""
