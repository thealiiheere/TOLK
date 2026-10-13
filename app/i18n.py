"""Backend translations (uz / ru / en) for API errors, Telegram notifications and bot texts.

Routers raise ApiError("key"); the handler in main.py translates it using the X-Lang /
Accept-Language request header. Frontend UI strings live in app/static/js/i18n.js.
"""
from fastapi import HTTPException

DEFAULT_LANG = "uz"
SUPPORTED = ("uz", "ru", "en")

MESSAGES: dict[str, dict[str, str]] = {
    # --- auth ---
    "auth_required": {
        "uz": "Avval tizimga kiring",
        "ru": "Необходима авторизация",
        "en": "Please sign in first",
    },
    "forbidden": {
        "uz": "Bu bo'limga kirish huquqingiz yo'q",
        "ru": "У вас нет доступа к этому разделу",
        "en": "You don't have access to this section",
    },
    "tg_auth_invalid": {
        "uz": "Telegram ma'lumotlarini tekshirib bo'lmadi",
        "ru": "Не удалось проверить данные Telegram",
        "en": "Telegram sign-in data could not be verified",
    },
    "tg_auth_expired": {
        "uz": "Telegram sessiyasi eskirgan. Ilovani qayta oching",
        "ru": "Сессия Telegram устарела. Откройте приложение заново",
        "en": "Telegram session expired. Please reopen the app",
    },
    "tg_not_configured": {
        "uz": "Telegram orqali kirish sozlanmagan",
        "ru": "Вход через Telegram не настроен",
        "en": "Telegram sign-in is not configured",
    },
    "demo_disabled": {
        "uz": "Demo rejim o'chirilgan",
        "ru": "Демо-режим отключён",
        "en": "Demo mode is disabled",
    },
    "user_not_found": {
        "uz": "Foydalanuvchi topilmadi",
        "ru": "Пользователь не найден",
        "en": "User not found",
    },
    "onboarding_required": {
        "uz": "Avval ro'yxatdan o'tishni yakunlang",
        "ru": "Сначала завершите регистрацию",
        "en": "Please finish signing up first",
    },
    "already_onboarded": {
        "uz": "Siz allaqachon ro'yxatdan o'tgansiz",
        "ru": "Вы уже зарегистрированы",
        "en": "You have already signed up",
    },
    "tutor_not_approved": {
        "uz": "O'qituvchi arizangiz hali tasdiqlanmagan",
        "ru": "Ваша заявка преподавателя ещё не одобрена",
        "en": "Your teacher application has not been approved yet",
    },
    "account_blocked": {
        "uz": "Hisobingiz bloklangan. Administratorga murojaat qiling",
        "ru": "Ваш аккаунт заблокирован. Обратитесь к администратору",
        "en": "Your account is blocked. Please contact the administrator",
    },
    # --- not found ---
    "group_not_found": {"uz": "Guruh topilmadi", "ru": "Группа не найдена", "en": "Class not found"},
    "lesson_not_found": {"uz": "Dars topilmadi", "ru": "Урок не найден", "en": "Lesson not found"},
    "payment_not_found": {"uz": "To'lov topilmadi", "ru": "Платёж не найден", "en": "Payment not found"},
    "student_not_found": {"uz": "O'quvchi topilmadi", "ru": "Ученик не найден", "en": "Student not found"},
    "tutor_not_found": {
        "uz": "O'qituvchi topilmadi yoki tasdiqlanmagan",
        "ru": "Преподаватель не найден или не одобрен",
        "en": "Teacher not found or not approved",
    },
    # --- enrollment / payments ---
    "group_full": {
        "uz": "Guruhda bo'sh joy qolmagan",
        "ru": "В группе нет свободных мест",
        "en": "This class is full",
    },
    "group_unavailable": {
        "uz": "Bu guruhga hozircha yozilib bo'lmaydi",
        "ru": "Запись в эту группу сейчас недоступна",
        "en": "Enrollment for this class is not available",
    },
    "already_enrolled": {
        "uz": "Siz allaqachon ushbu guruhdasiz",
        "ru": "Вы уже состоите в этой группе",
        "en": "You are already enrolled in this class",
    },
    "payment_pending_exists": {
        "uz": "Bu guruh uchun to'lovingiz allaqachon tekshirilmoqda",
        "ru": "Ваш платёж за эту группу уже на проверке",
        "en": "Your payment for this class is already being reviewed",
    },
    "payment_already_reviewed": {
        "uz": "Bu to'lov allaqachon ko'rib chiqilgan",
        "ru": "Этот платёж уже рассмотрен",
        "en": "This payment has already been reviewed",
    },
    "receipt_required": {
        "uz": "To'lov chekini yuklang",
        "ru": "Прикрепите чек об оплате",
        "en": "Please attach the payment receipt",
    },
    "receipt_too_large": {
        "uz": "Fayl juda katta (maksimum {mb} MB)",
        "ru": "Файл слишком большой (максимум {mb} МБ)",
        "en": "File is too large (max {mb} MB)",
    },
    "receipt_bad_type": {
        "uz": "Faqat JPG, PNG, WEBP yoki PDF fayllar qabul qilinadi",
        "ru": "Принимаются только файлы JPG, PNG, WEBP или PDF",
        "en": "Only JPG, PNG, WEBP or PDF files are accepted",
    },
    "not_enrolled": {
        "uz": "Siz bu guruhda emassiz",
        "ru": "Вы не состоите в этой группе",
        "en": "You are not enrolled in this class",
    },
    "access_revoked": {
        "uz": "3 ta ogohlantirish sababli guruhga kirish yopilgan",
        "ru": "Доступ к группе закрыт из-за 3 страйков",
        "en": "Access to this class is closed because of 3 strikes",
    },
    # --- lessons / ratings ---
    "lesson_not_scheduled": {
        "uz": "Bu dars allaqachon yakunlangan yoki bekor qilingan",
        "ru": "Этот урок уже завершён или отменён",
        "en": "This lesson is already completed or cancelled",
    },
    "lesson_not_completed": {
        "uz": "Darsni faqat u tugaganidan keyin baholash mumkin",
        "ru": "Оценить урок можно только после его завершения",
        "en": "You can rate a lesson only after it is completed",
    },
    "lesson_absent": {
        "uz": "Siz bu darsda qatnashmagansiz",
        "ru": "Вы не присутствовали на этом уроке",
        "en": "You did not attend this lesson",
    },
    "already_rated": {
        "uz": "Siz bu darsni allaqachon baholagansiz",
        "ru": "Вы уже оценили этот урок",
        "en": "You have already rated this lesson",
    },
    "group_has_no_tutor": {
        "uz": "Guruhga o'qituvchi biriktirilmagan",
        "ru": "У группы нет преподавателя",
        "en": "This class has no teacher assigned",
    },
    "tutor_profile_incomplete": {
        "uz": "O'qituvchi sifatida ro'yxatdan o'tish uchun fanlar va o'zingiz haqingizda (kamida 20 belgi) yozing",
        "ru": "Для регистрации преподавателем укажите предметы и расскажите о себе (не менее 20 символов)",
        "en": "To sign up as a teacher, list your subjects and write about yourself (at least 20 characters)",
    },
    "meeting_link_reused": {
        "uz": "Bu havola avvalgi darsda ishlatilgan. Har bir dars uchun yangi Zoom / Google Meet havolasini kiriting",
        "ru": "Эта ссылка уже использовалась. Для каждого урока нужна новая ссылка Zoom / Google Meet",
        "en": "This link was already used. Each lesson needs a new Zoom / Google Meet link",
    },
    "lesson_time_invalid": {
        "uz": "Dars vaqti noto'g'ri: kelajakdagi sanani tanlang (180 kungacha)",
        "ru": "Неверное время урока: выберите дату в будущем (до 180 дней)",
        "en": "Invalid lesson time: choose a future date (up to 180 days ahead)",
    },
    "lesson_not_started": {
        "uz": "Dars hali boshlanmagan",
        "ru": "Урок ещё не начался",
        "en": "This lesson hasn't started yet",
    },
    "max_below_enrolled": {
        "uz": "Guruhda allaqachon {n} o'quvchi bor — o'rinlar soni bundan kam bo'lishi mumkin emas",
        "ru": "В группе уже {n} учеников — мест не может быть меньше",
        "en": "The class already has {n} students — seats can't be lower than that",
    },
    "already_enrolled_admin": {
        "uz": "O'quvchi allaqachon ushbu guruhda",
        "ru": "Ученик уже состоит в этой группе",
        "en": "The student is already in this class",
    },
    "cannot_block_admin": {
        "uz": "Administratorni bloklab bo'lmaydi",
        "ru": "Нельзя заблокировать администратора",
        "en": "Administrators can't be blocked",
    },
    "invalid_course_code": {
        "uz": "Kurs kodi: 2–20 ta lotin harfi, raqam yoki «-» (masalan, ENG-101)",
        "ru": "Код курса: 2–20 латинских букв, цифр или «-» (например, ENG-101)",
        "en": "Course code: 2–20 Latin letters, digits or \"-\" (e.g. ENG-101)",
    },
    "course_code_taken": {
        "uz": "{code} kodi boshqa kursda ishlatilgan",
        "ru": "Код {code} уже используется другим курсом",
        "en": "The code {code} is already used by another class",
    },
    "certificates_required": {
        "uz": "Kamida bitta sertifikat yoki diplom yuklang (JPG, PNG, WEBP yoki PDF)",
        "ru": "Загрузите хотя бы один сертификат или диплом (JPG, PNG, WEBP или PDF)",
        "en": "Upload at least one certificate or diploma (JPG, PNG, WEBP or PDF)",
    },
    "too_many_documents": {
        "uz": "Bir martada {per_upload} tagacha, jami {total} tagacha hujjat yuklash mumkin",
        "ru": "Можно загрузить до {per_upload} файлов за раз и до {total} всего",
        "en": "You can upload up to {per_upload} files at a time and {total} in total",
    },
    "tutor_no_documents": {
        "uz": "O'qituvchi hech qanday sertifikat yuklamagan — tasdiqlab bo'lmaydi",
        "ru": "Преподаватель не загрузил ни одного сертификата — одобрить нельзя",
        "en": "This teacher hasn't uploaded any certificates, so they can't be approved",
    },
    "document_not_found": {"uz": "Hujjat topilmadi", "ru": "Документ не найден", "en": "Document not found"},
    "invalid_language_code": {
        "uz": "Til kursi uchun tilni ro'yxatdan tanlang",
        "ru": "Для языкового курса выберите язык из списка",
        "en": "Pick a language from the list for a language class",
    },
    "not_found": {"uz": "Topilmadi", "ru": "Не найдено", "en": "Not found"},
    # --- validation ---
    "invalid_meeting_link": {
        "uz": "Zoom yoki Google Meet uchun to'g'ri https havola kiriting",
        "ru": "Укажите корректную https-ссылку на Zoom или Google Meet",
        "en": "Enter a valid https Zoom or Google Meet link",
    },
    "invalid_url": {
        "uz": "To'g'ri havola kiriting (http:// yoki https://)",
        "ru": "Укажите корректную ссылку (http:// или https://)",
        "en": "Enter a valid link (http:// or https://)",
    },
    "validation_error": {
        "uz": "Ma'lumotlar noto'g'ri to'ldirilgan",
        "ru": "Данные заполнены некорректно",
        "en": "Some fields are invalid",
    },
    "server_error": {
        "uz": "Serverda xatolik yuz berdi",
        "ru": "Произошла ошибка сервера",
        "en": "Something went wrong on the server",
    },
    # --- Telegram notifications (HTML parse mode; values are escaped by notify.py) ---
    "n_payment_approved": {
        "uz": "✅ To'lov tasdiqlandi! Siz «{group}» guruhiga qabul qilindingiz.",
        "ru": "✅ Оплата подтверждена! Вы зачислены в группу «{group}».",
        "en": "✅ Payment confirmed! You are now enrolled in «{group}».",
    },
    "n_payment_rejected": {
        "uz": "❌ «{group}» uchun to'lov rad etildi. {comment}",
        "ru": "❌ Оплата за «{group}» отклонена. {comment}",
        "en": "❌ Your payment for «{group}» was rejected. {comment}",
    },
    "n_lesson_scheduled": {
        "uz": "📅 «{group}» guruhida yangi dars: {when}\n{topic}\nDars havolasi ilovada.",
        "ru": "📅 Новый урок в группе «{group}»: {when}\n{topic}\nСсылка на урок — в приложении.",
        "en": "📅 New lesson in «{group}»: {when}\n{topic}\nThe meeting link is in the app.",
    },
    "n_lesson_updated": {
        "uz": "🔄 «{group}» guruhidagi dars yangilandi: {when}. Yangi havola ilovada.",
        "ru": "🔄 Урок в группе «{group}» обновлён: {when}. Новая ссылка — в приложении.",
        "en": "🔄 The lesson in «{group}» was updated: {when}. The new link is in the app.",
    },
    "n_lesson_cancelled": {
        "uz": "🚫 «{group}» guruhidagi {when} darsi bekor qilindi.",
        "ru": "🚫 Урок в группе «{group}» ({when}) отменён.",
        "en": "🚫 The lesson in «{group}» on {when} was cancelled.",
    },
    "n_rate_lesson": {
        "uz": "⭐ «{group}» guruhidagi dars qanday o'tdi? Ilovada 1 dan 5 gacha baho bering.",
        "ru": "⭐ Как прошёл урок в группе «{group}»? Оцените его от 1 до 5 в приложении.",
        "en": "⭐ How was the lesson in «{group}»? Rate it from 1 to 5 in the app.",
    },
    "n_tutor_approved": {
        "uz": "🎉 O'qituvchi arizangiz tasdiqlandi! Administrator sizni guruhlarga biriktiradi.",
        "ru": "🎉 Ваша заявка преподавателя одобрена! Администратор назначит вам группы.",
        "en": "🎉 Your teacher application was approved! The admin will assign classes to you.",
    },
    "n_tutor_rejected": {
        "uz": "Afsuski, o'qituvchi arizangiz rad etildi. {reason}\nIlovada yangi hujjatlarni yuklab, qayta ariza berishingiz mumkin.",
        "ru": "К сожалению, ваша заявка преподавателя отклонена. {reason}\nВы можете загрузить новые документы в приложении и подать заявку снова.",
        "en": "Unfortunately, your teacher application was declined. {reason}\nYou can upload new documents in the app to apply again.",
    },
    "n_group_assigned": {
        "uz": "📚 Sizga yangi guruh biriktirildi: «{group}».",
        "ru": "📚 Вам назначена новая группа: «{group}».",
        "en": "📚 You have been assigned a new class: «{group}».",
    },
    "n_admin_payment": {
        "uz": "💳 Yangi to'lov: {student} — «{group}», {amount} so'm",
        "ru": "💳 Новый платёж: {student} — «{group}», {amount} сум",
        "en": "💳 New payment: {student} — «{group}», {amount} UZS",
    },
    "n_admin_tutor": {
        "uz": "🎓 Yangi o'qituvchi arizasi: {name} ({n} ta hujjat)",
        "ru": "🎓 Новая заявка преподавателя: {name} (документов: {n})",
        "en": "🎓 New teacher application: {name} ({n} documents)",
    },
    "n_admin_tutor_docs": {
        "uz": "📎 {name} {n} ta yangi hujjat yukladi — tekshiring",
        "ru": "📎 {name}: загружены новые документы ({n}) — проверьте",
        "en": "📎 {name} uploaded {n} new document(s) — please review",
    },
    "open_app": {"uz": "TOLK ni ochish", "ru": "Открыть TOLK", "en": "Open TOLK"},
    # --- bot ---
    "bot_welcome": {
        "uz": (
            "Assalomu alaykum, {name}! 👋\n\n"
            "<b>TOLK</b> — o'quvchilar va o'qituvchilarni bog'laydigan ta'lim platformasi. "
            "Til va boshqa fanlar bo'yicha kichik guruhlarda onlayn darslar.\n\n"
            "Boshlash uchun quyidagi tugmani bosing 👇"
        ),
        "ru": (
            "Привет, {name}! 👋\n\n"
            "<b>TOLK</b> — образовательная платформа, которая помогает ученикам и преподавателям найти друг друга. "
            "Онлайн-занятия в мини-группах по языкам и другим предметам.\n\n"
            "Нажмите кнопку ниже, чтобы начать 👇"
        ),
        "en": (
            "Hi, {name}! 👋\n\n"
            "<b>TOLK</b> is an education platform that helps students and teachers find each other. "
            "Online classes in small groups for languages and other subjects.\n\n"
            "Tap the button below to get started 👇"
        ),
    },
}


class ApiError(HTTPException):
    def __init__(self, key: str, status_code: int = 400, **params):
        super().__init__(status_code=status_code, detail=key)
        self.key = key
        self.params = params


def normalize_lang(value: str | None) -> str:
    if not value:
        return DEFAULT_LANG
    code = value.strip().lower()[:2]
    return code if code in SUPPORTED else DEFAULT_LANG


def lang_from_headers(headers) -> str:
    explicit = headers.get("x-lang")
    if explicit:
        return normalize_lang(explicit)
    accept = headers.get("accept-language", "")
    for part in accept.split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in SUPPORTED:
            return code
    return DEFAULT_LANG


def t(key: str, lang: str = DEFAULT_LANG, **params) -> str:
    entry = MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry[DEFAULT_LANG]
    return text.format(**params) if params else text
