"""Arabic UI strings keyed by (Qt translation context, English source).

Missing keys fall back to English (empty translation). Context names match QObject.tr / qsTr rules:
Python: class name (e.g. ChatController). QML Main.qml: Main.
"""

from __future__ import annotations

# fmt: off
AR_UI: dict[tuple[str, str], str] = {
    # --- Main.qml (context Main) ---
    ("Main", "🎙️ Meeting Assistant"): "🎙️ مساعد الاجتماعات",
    ("Main", "Import audio file"): "استيراد ملف صوتي",
    ("Main", "🗂️ Local AI Meeting Assistant"): "🗂️ مساعد اجتماعات بالذكاء الاصطناعي محليًا",
    ("Main", "Status"): "الحالة",
    ("Main", "Generating summary with the local model…"): "جارٍ إنشاء الملخص بالنموذج المحلي…",
    ("Main", "Transcribing audio with WhisperX…"): "جارٍ نسخ الصوت بواسطة WhisperX…",
    ("Main", "Working…"): "جارٍ العمل…",
    ("Main", "Stop"): "إيقاف",
    ("Main", "Stop processing?"): "إيقاف المعالجة؟",
    ("Main", "This will request to stop transcription or summarization. The current step may take a moment to finish (especially while the local speech or language model is working). Do you want to stop?"):
        "سيُطلب إيقاف النسخ أو التلخيص. قد تستغرق الخطوة الحالية لحظات حتى تتوقف (خصوصًا أثناء عمل نموذج الكلام أو اللغة المحلي). هل تريد الإيقاف؟",
    ("Main", "☀️ Light"): "☀️ فاتح",
    ("Main", "🌙 Dark"): "🌙 داكن",
    ("Main", "English"): "English",
    ("Main", "العربية"): "العربية",
    ("Main", "⚙️ Settings"): "⚙️ الإعدادات",
    ("Main", "➕ New session"): "➕ جلسة جديدة",
    ("Main", "📋 Sessions"): "📋 الجلسات",
    ("Main", "Rename"): "إعادة تسمية",
    ("Main", "Delete…"): "حذف…",
    ("Main", "Delete session and files from disk?"): "حذف الجلسة والملفات من القرص؟",
    ("Main", "Permanent data loss"): "فقدان دائم للبيانات",
    ("Main", "This removes real files and chat history. The app does not move them to the Recycle Bin — they are deleted from the session folder on disk."):
        "سُتحذف ملفات حقيقية وسجل المحادثة. التطبيق لا ينقلها إلى سلة المحذوفات — تُحذف من مجلد الجلسة على القرص.",
    ("Main", "Session: \"%1\"\n\n• All messages in this session\n• The whole meeting folder under \"sessions\" (audio, transcripts, summaries, and anything else inside that folder)\n\nOnly click the red button if you accept complete loss of this data."):
        "الجلسة: «%1»\n\n• جميع رسائل هذه الجلسة\n• مجلد الاجتماع كاملًا ضمن «sessions» (الصوت، النصوص المفرغة، الملخصات، وأي ملفات أخرى داخل ذلك المجلد)\n\nلا تضغط الزر الأحمر إلا إذا تقبل فقدان هذه البيانات بالكامل.",
    ("Main", "Delete session and all disk files"): "حذف الجلسة وكل ملفات القرص",
    ("Main", "Delete Whisper model from disk?"): "حذف نموذج Whisper من القرص؟",
    ("Main", "You are about to delete large model files from your disk. This is not undoable here — you must download the weights again for offline speech."):
        "أنت على وشك حذف ملفات نموذج كبيرة من القرص. لا يمكن التراجع هنا — يجب إعادة تنزيل الأوزان للنسخ الصوتي دون اتصال.",
    ("Main", "The entire Whisper / WhisperX cache folder will be erased (often several gigabytes). Offline transcription will not work until you use \"Download / resume\" again.\n\nOnly use the red button if you intend to free disk space and accept re-downloading."):
        "سيُمحى مجلد ذاكرة Whisper / WhisperX بالكامل (غالبًا عدة غيغابايت). لن يعمل النسخ دون اتصال حتى تستخدم «تنزيل / استئناف» مجددًا.\n\nاستخدم الزر الأحمر فقط إذا أردت تفريغ مساحة القرص وقبول إعادة التنزيل.",
    ("Main", "Delete model files from disk"): "حذف ملفات النموذج من القرص",
    ("Main", "Delete model from disk…"): "حذف النموذج من القرص…",
    ("Main", "No messages yet.\n📎 Drop an audio file here, use 📂 Import, or use 🎤 Record to capture your microphone."):
        "لا توجد رسائل بعد.\n📎 أسقط ملفًا صوتيًا هنا، أو استخدم 📂 استيراد، أو 🎤 تسجيل من الميكروفون.",
    ("Main", "Generating summary with local LLM…"): "جارٍ إنشاء الملخص بالنموذج اللغوي المحلي…",
    ("Main", "Transcribing with WhisperX…"): "جارٍ النسخ باستخدام WhisperX…",
    ("Main", "Transcript"): "النص المفرغ",
    ("Main", "Summary"): "الملخص",
    ("Main", "Assistant"): "المساعد",
    ("Main", "Warning"): "تحذير",
    ("Main", "Info"): "معلومات",
    ("Main", "Error"): "خطأ",
    ("Main", "📂 Open transcript file"): "📂 فتح ملف النص المفرغ",
    ("Main", "Summarize again"): "تلخيص مجددًا",
    ("Main", "📂 Open summary file"): "📂 فتح ملف الملخص",
    ("Main", "📂 Open file"): "📂 فتح الملف",
    ("Main", "Re-transcribe"): "إعادة النسخ",
    ("Main", "Try again"): "إعادة المحاولة",
    ("Main", "▼ "): "▼ ",
    ("Main", "▶ "): "▶ ",
    ("Main", "📎 Drop audio, Import a file, or record — press Send to set prompts and run the pipeline."):
        "📎 أسقط الصوت أو استورد ملفًا أو سجّل — اضغط إرسال لتعيين التوجيهات وتشغيل المسار.",
    ("Main", "Prompts before run"): "التوجيهات قبل التشغيل",
    ("Main", "Summarization prompt"): "توجيه التلخيص",
    ("Main", "Gemma (summarization instructions)"): "Gemma (تعليمات التلخيص)",
    ("Main", "Whisper (transcription context / initial prompt)"): "Whisper (سياق النسخ / التوجيه الأولي)",
    ("Main", "Summarize"): "تلخيص",
    ("Main", "Send or clear staged audio before starting a new recording."):
        "أرسل أو امسح الصوت المعلّق قبل بدء تسجيل جديد.",
    ("Main", "Clear staged"): "مسح المعلّق",
    ("Main", "Send"): "إرسال",
    ("Main", "📂 Import"): "📂 استيراد",
    ("Main", "⏹️ Stop recording"): "⏹️ إيقاف التسجيل",
    ("Main", "🎤 Record"): "🎤 تسجيل",
    ("Main", "Speech model (WhisperX)"): "نموذج الكلام (WhisperX)",
    ("Main", "✓ Model ready (offline STT)"): "✓ النموذج جاهز (نسخ صوتي دون اتصال)",
    ("Main", "⚠ Speech model not ready"): "⚠ نموذج الكلام غير جاهز",
    ("Main", "Weights are stored next to the project (you can move the whole folder). Cache:\n"):
        "الأوزان تُخزَّن بجوار المشروع (يمكنك نقل المجلد كاملًا). ذاكرة التخزين المؤقت:\n",
    ("Main", "Refresh status"): "تحديث الحالة",
    ("Main", "Downloading…"): "جارٍ التنزيل…",
    ("Main", "Download / resume"): "تنزيل / استئناف",
    ("Main", "Meeting files folder"): "مجلد ملفات الاجتماع",
    ("Main", "Copy"): "نسخ",
    ("Main", "Each session has a folder under \"sessions\" in this path (audio, transcript .txt, summary .txt). Older flat subfolders may still exist from previous versions."):
        "لكل جلسة مجلد ضمن «sessions» في هذا المسار (الصوت، النص المفرغ .txt، الملخص .txt). قد تبقى مجلدات فرعية قديمة مسطّحة من إصدارات سابقة.",
    ("Main", "Browse…"): "استعراض…",
    ("Main", "Use project default"): "استخدام المسار الافتراضي للمشروع",
    ("Main", "📋 Copy path"): "📋 نسخ المسار",
    (
        "Main",
        "Tip: List participant names, domain jargon, or uncommon words you expect in this meeting. "
        "That vocabulary helps the model guess clearer spellings—especially for English terms.",
    ):
        "تلميح: اذكر أسماء المشاركين، مصطلحات المجال، أو الكلمات غير الشائعة التي تتوقعها في الاجتماع؛ "
        "فذلك يساعد النموذج على تخمين تهجئة أوضح، خصوصًا للمفردات الإنجليزية.",
    ("Main", "📋 Copy data folder path"): "📋 نسخ مسار مجلد البيانات",
    ("Main", "📋 Copy meeting files folder"): "📋 نسخ مجلد ملفات الاجتماع",
    ("Main", "✖️ Close"): "✖️ إغلاق",
    ("Main", "Rename session"): "إعادة تسمية الجلسة",
    ("Main", "Session title"): "عنوان الجلسة",
    ("Main", "Cancel"): "إلغاء",
    ("Main", "Debug"): "تصحيح",
    ("Main", "Choose meeting files folder"): "اختر مجلد ملفات الاجتماع",
    ("Main", "Ready: %1"): "جاهز: %1",
    ("Main", "ETA %1"): "الوقت المتبقي %1",
    # --- ChatController ---
    ("ChatController", "User"): "المستخدم",
    ("ChatController", "Transcript"): "النص المفرغ",
    ("ChatController", "Summary"): "الملخص",
    ("ChatController", "Assistant"): "المساعد",
    ("ChatController", "Warning"): "تحذير",
    ("ChatController", "Info"): "معلومات",
    ("ChatController", "Message copied to clipboard."): "تم نسخ الرسالة إلى الحافظة.",
    ("ChatController", "Audio ({0})"): "صوت ({0})",
    ("ChatController", "All files (*)"): "جميع الملفات (*)",
    ("ChatController", "No active session."): "لا توجد جلسة نشطة.",
    ("ChatController", "Already processing."): "المعالجة جارية بالفعل.",
    (
        "ChatController",
        "Finish or cancel speaker naming in another session before starting a new run.",
    ): "أنهِ أو ألغِ تسمية المتحدثين في جلسة أخرى قبل بدء تشغيل جديد.",
    (
        "ChatController",
        "Finish or cancel speaker naming before starting a new run.",
    ): "أنهِ أو ألغِ تسمية المتحدثين قبل بدء تشغيل جديد.",
    (
        "ChatController",
        "Finish or cancel speaker naming before importing another file.",
    ): "أنهِ أو ألغِ تسمية المتحدثين قبل استيراد ملف آخر.",
    ("ChatController", "Stop recording before importing a file."): "أوقف التسجيل قبل استيراد ملف.",
    ("ChatController", "Invalid file path."): "مسار الملف غير صالح.",
    ("ChatController", "Folders are not supported — choose an audio file: {0}"):
        "المجلدات غير مدعومة — اختر ملفًا صوتيًا: {0}",
    ("ChatController", "File not found: {0}"): "الملف غير موجود: {0}",
    ("ChatController", "Not supported audio ({0}): {1}. Use one of: {2}"):
        "صيغة غير مدعومة ({0}): {1}. استخدم إحدى: {2}",
    ("ChatController", "Replaced staged file — now: {0}"): "استُبدل الملف المعلّق — الآن: {0}",
    ("ChatController", "Ready to send — audio file: {0}"): "جاهز للإرسال — ملف الصوت: {0}",
    ("ChatController", "Drop did not contain any file paths."): "الإفلات لا يحتوي على مسارات ملفات.",
    ("ChatController", "Drop one audio file at a time."): "أسقط ملفًا صوتيًا واحدًا في كل مرة.",
    ("ChatController", "Could not read dropped file path."): "تعذّر قراءة مسار الملف المُفلات.",
    ("ChatController", "Folders are not supported — drop an audio file: {0}"):
        "المجلدات غير مدعومة — أسقط ملفًا صوتيًا: {0}",
    ("ChatController", "Not a file or no longer exists: {0}"): "ليس ملفًا أو لم يعد موجودًا: {0}",
    ("ChatController", "Staged file cleared."): "تم مسح الملف المعلّق.",
    ("ChatController", "Stop recording first, then press Send to run the pipeline."):
        "أوقف التسجيل أولًا ثم اضغط إرسال لتشغيل المسار.",
    (
        "ChatController",
        "Nothing to send yet. Use Record (then Stop recording) or drop an audio file on this window, then press Send to set prompts and run the pipeline.",
    ): "لا يوجد شيء للإرسال بعد. استخدم التسجيل (ثم أوقف التسجيل) أو أسقط ملفًا صوتيًا في هذه النافذة، ثم اضغط إرسال لتعيين التوجيهات وتشغيل المسار.",
    (
        "ChatController",
        "No audio staged. After you stop recording or drop a file, it appears as ready; then press Send to set prompts and run the pipeline.",
    ): "لا يوجد صوت معلّق. بعد إيقاف التسجيل أو إفلات ملف يظهر كجاهز؛ ثم اضغط إرسال لتعيين التوجيهات وتشغيل المسار.",
    ("ChatController", "Speech model missing — open Settings and download Whisper."):
        "نموذج الكلام غير موجود — افتح الإعدادات ونزّل Whisper.",
    ("ChatController", "File not found."): "الملف غير موجود.",
    ("ChatController", "No recording file."): "لا يوجد ملف تسجيل.",
    ("ChatController", "Send or clear the staged audio file before recording."):
        "أرسل أو امسح الملف الصوتي المعلّق قبل التسجيل.",
    ("ChatController", "Transcribing…"): "جارٍ النسخ…",
    ("ChatController", "Generating summary…"): "جارٍ إنشاء الملخص…",
    ("ChatController", "Done."): "تم.",
    ("ChatController", "Error"): "خطأ",
    ("ChatController", "Message not found."): "الرسالة غير موجودة.",
    ("ChatController", "Only http and https links can be opened."): "لا يمكن فتح إلا روابط http و https.",
    ("ChatController", "Invalid link."): "رابط غير صالح.",
    ("ChatController", "Select a transcript message to summarize again."):
        "اختر رسالة النص المفرغ لإعادة التلخيص.",
    ("ChatController", "Transcript is empty."): "النص المفرغ فارغ.",
    ("ChatController", "File no longer exists."): "الملف لم يعد موجودًا.",
    ("ChatController", "Data path copied to clipboard."): "تم نسخ مسار البيانات إلى الحافظة.",
    ("ChatController", "Meeting files folder copied to clipboard."): "تم نسخ مجلد ملفات الاجتماع إلى الحافظة.",
    ("ChatController", "Processing was stopped."): "تم إيقاف المعالجة.",
    ("ChatController", "Summarization was skipped because you stopped processing."):
        "تم تخطي التلخيص لأنك أوقفت المعالجة.",
    ("ChatController", "Summarization was stopped."): "تم إيقاف التلخيص.",

    # --- ModelStatusController ---
    ("ModelStatusController", "{0} B"): "{0} بايت",
    ("ModelStatusController", "{0:.1f} KB"): "{0:.1f} ك.ب",
    ("ModelStatusController", "{0:.1f} MB"): "{0:.1f} م.ب",
    ("ModelStatusController", "{0:.2f} GB"): "{0:.2f} ج.ب",
    ("ModelStatusController", "—"): "—",
    ("ModelStatusController", "{0:.1f} steps/s"): "{0:.1f} خطوة/ث",
    ("ModelStatusController", "{0:.1f} MB/s"): "{0:.1f} م.ب/ث",
    ("ModelStatusController", "{0:.1f} KB/s"): "{0:.1f} ك.ب/ث",
    ("ModelStatusController", "{0}s"): "{0} ث",
    ("ModelStatusController", "{0}m {1}s"): "{0} د {1} ث",
    ("ModelStatusController", "{0}h {1}m"): "{0} س {1} د",
    ("ModelStatusController", "…"): "…",
    ("ModelStatusController", "{0:.0f}%"): "{0:.0f}٪",
    ("ModelStatusController", "{0} / {1}"): "{0} / {1}",
    ("ModelStatusController", "{0} downloaded"): "{0} تم تنزيلها",
    ("ModelStatusController", "Starting…"): "بدء…",
    ("ModelStatusController", "WhisperX · {0} · language={1}"): "WhisperX · {0} · اللغة={1}",
    ("ModelStatusController", " · align={0}"): " · محاذاة={0}",
    ("ModelStatusController", "No Hugging Face token — add it in Settings (or set MEETING_ASSISTANT_HF_TOKEN) for speaker diarization (accept pyannote model conditions on huggingface.co first)."):
        "لا يوجد رمز Hugging Face — أضِفه في الإعدادات (أو عيّن MEETING_ASSISTANT_HF_TOKEN) لتفرقة المتحدثين (اقبل شروط نموذج pyannote على huggingface.co أولًا).",
    ("ModelStatusController", "Model not installed. Use Download to fetch Whisper weights (~several GB for large-v3)."):
        "النموذج غير مثبّت. استخدم التنزيل لجلب أوزان Whisper (~عدة غيغابايت للنموذج large-v3).",
    ("ModelStatusController", "Download incomplete or cache is damaged — press Download to resume, or remove cached files to start over."):
        "التنزيل غير مكتمل أو الذاكرة المؤقتة تالفة — اضغط تنزيل للاستئناف، أو احذف الملفات المخزَّنة للبدء من جديد.",

    # --- RecordingController ---
    ("RecordingController", "Qt Multimedia recorder unavailable."): "مسجّل Qt Multimedia غير متاح.",
    ("RecordingController", "Recording folder is not set."): "لم يُضبط مجلد التسجيل.",
    ("RecordingController", "Cannot create recording folder: {0}"): "تعذّر إنشاء مجلد التسجيل: {0}",

    # --- SessionController ---
    ("SessionController", "Welcome"): "مرحبًا",
    ("SessionController", "New meeting"): "اجتماع جديد",
    ("SessionController", "Untitled"): "بدون عنوان",
    ("SessionController", "Could not rename meeting folder: {0}"): "تعذّرت إعادة تسمية مجلد الاجتماع: {0}",
    ("SessionController", "Some meeting files could not be deleted: {0}"): "تعذّر حذف بعض ملفات الاجتماع: {0}",

    # --- ChatController (speaker mapping) ---
    ("ChatController", "Name each speaker, then confirm to generate the summary."):
        "سمِّ كل متحدث ثم أكّد لإنشاء الملخص.",
    ("ChatController", "Speaker naming was cancelled."): "أُلغي تسمية المتحدثين.",
    ("ChatController", "Speaker names"): "أسماء المتحدثين",
    ("ChatController", "Invalid speaker data."): "بيانات المتحدثين غير صالحة.",
    ("ChatController", "No voice sample time range for this speaker."):
        "لا يوجد مقطع زمني لعيّنة صوت هذا المتحدث.",
    ("ChatController", "Audio file is not available for playback."):
        "ملف الصوت غير متاح للتشغيل.",

    # --- Main.qml (HF + speaker card) ---
    ("Main", "Speaker diarization"): "تفرقة المتحدثين",
    ("Main", "When enabled, transcripts label each speaker (SPEAKER_00, …) and may pause for naming. Requires a Hugging Face token. When disabled, transcription uses timestamps only and does not need a token."):
        "عند التفعيل، تُوسِم النصوص كل متحدث (SPEAKER_00، …) وقد تتوقف لطلب الأسماء. يتطلب رمز Hugging Face. عند التعطيل، يستخدم التفريغ الطوابع الزمنية فقط ولا يحتاج رمزًا.",
    ("Main", "Hugging Face token (required for speaker diarization)"):
        "رمز Hugging Face (مطلوب لتفرقة المتحدثين)",
    ("Main", "Hugging Face token (pyannote / speaker diarization)"):
        "رمز Hugging Face (pyannote / تفرقة المتحدثين)",
    ("Main", "Create a token at huggingface.co (read access). Accept the pyannote model conditions on the Hub first. The token is stored only on this device."):
        "أنشئ رمزًا على huggingface.co (صلاحية قراءة). اقبل شروط نموذج pyannote على المنصة أولًا. يُخزَّن الرمز على هذا الجهاز فقط.",
    ("Main", "Paste hf_… token (leave empty to keep current)"):
        "الصق رمز hf_… (اتركه فارغًا للإبقاء على المخزَّن)",
    ("Main", "Diarization complete — name each speaker, then confirm to generate the summary."):
        "اكتملت تفرقة المتحدثين — سمِّ كل متحدث ثم أكّد لإنشاء الملخص.",
    ("Main", "Display name"): "اسم العرض",
    ("Main", "Confirm and generate summary"): "تأكيد وإنشاء الملخص",
    ("Main", "Use default labels"): "استخدام التسميات الافتراضية",
}
