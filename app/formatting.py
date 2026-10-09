"""Telegram message (HTML) in Azerbaijani for a Verdict."""
from html import escape

from app.schemas import Verdict

HEADLINES = {
    "scam": "🔴 <b>Bu, fırıldaqdır!</b>",
    "suspicious": "🟡 <b>Şübhəlidir, ehtiyatlı olun</b>",
    "safe": "🟢 <b>Təhlükəsiz görünür</b>",
}

LINK_WARNINGS = {
    "lookalike": "rəsmi sayta oxşayır, amma saxtadır",
    "suspicious": "şübhəli domen",
    "shortener": "qısaldılmış link, haraya apardığı bilinmir",
}

START_TEXT = (
    "👋 <b>Salam! Mən Unhook-am.</b>\n"
    "<i>Fırıldaqçıya tutulmadan əvvəl xilas ol.</i>\n\n"
    "Şübhəli mesaj və ya ekran görüntüsü aldınızsa, mənə göndərin. Mən yoxlayıb deyim:\n"
    "• fırıldaqdırmı,\n• hansı üsuldur,\n• nə etmək lazımdır.\n\n"
    "📩 Mesajı <b>yönləndirin (forward)</b>, mətni yapışdırın və ya <b>şəkil</b> göndərin.\n"
    "Azərbaycan dilində, translitlə (məs. <i>\"bonusunuz hazirdir\"</i>) və rus dili qarışıq yazılmış mesajları başa düşürəm.\n\n"
    "👨‍👩‍👧 <b>Qrupda:</b> məni ailə qrupuna əlavə edin. Qrupda linkli şübhəli mesaj görsəm xəbərdarlıq edərəm. "
    "İstədiyiniz mesaja cavab verib <b>/yoxla</b> yazsanız onu yoxlayaram.\n\n"
    "🔒 Kart nömrələri, telefonlar və təsdiq kodları saxlanmadan əvvəl silinir."
)

THINKING_TEXT = "🔎 Yoxlayıram, bir neçə saniyə gözləyin..."
ERROR_TEXT = "😔 Yoxlama zamanı xəta baş verdi. Bir az sonra yenidən cəhd edin."
NO_INPUT_TEXT = "Mətn və ya şəkil göndərin, yoxlayım."


REPLY_TO_CHECK_TEXT = "Yoxlamaq istədiyiniz mesaja <b>cavab verib</b> /yoxla yazın."


def age_phrase(days: int) -> str:
    return "bu gün" if days == 0 else f"{days} gün əvvəl"


def format_group_warning(v: Verdict) -> str:
    """Short warning for a family group: headline, scheme, one-line explanation, first action."""
    lines = [HEADLINES[v.verdict]]
    if v.scheme != "none":
        lines.append(f"📌 {escape(v.scheme_az)}")
    if v.explanation_az:
        lines.append(escape(v.explanation_az))
    for l in v.links:
        if l.status in LINK_WARNINGS:
            lines.append(f"🔗 <code>{escape(l.domain)}</code>: {LINK_WARNINGS[l.status]}")
            break
    if v.actions:
        lines.append(f"👉 {escape(v.actions[0])}")
    return "\n".join(lines)


def format_verdict(v: Verdict) -> str:
    lines = [HEADLINES[v.verdict]]
    if v.scheme != "none":
        lines.append(f"📌 <b>Üsul:</b> {escape(v.scheme_az)}")
    if v.explanation_az:
        lines.append(f"\n{escape(v.explanation_az)}")

    if v.reasons:
        lines.append("\n<b>Niyə?</b>")
        lines += [f"• {escape(r)}" for r in v.reasons]

    bad_links = [l for l in v.links if l.status in LINK_WARNINGS]
    for l in bad_links:
        lines.append(f"🔗 <code>{escape(l.domain)}</code>: {LINK_WARNINGS[l.status]}")
    for l in v.links:
        if l.age_days is not None and l.age_days < 90:
            lines.append(f"🕒 <code>{escape(l.domain)}</code> saytı {age_phrase(l.age_days)} yaradılıb. Yeni saytlara ehtiyatla yanaşın.")

    if v.actions:
        lines.append("\n<b>Nə etməli?</b>")
        lines += [f"{i}. {escape(a)}" for i, a in enumerate(v.actions, 1)]

    if v.degraded:
        lines.append("\n⚠️ <i>Tam avtomatik təhlil hazırda əlçatan deyil, yalnız linklər yoxlanıldı.</i>")
    else:
        lines.append(f"\n<i>Əminlik: {round(v.confidence * 100)}%</i>")
    return "\n".join(lines)
