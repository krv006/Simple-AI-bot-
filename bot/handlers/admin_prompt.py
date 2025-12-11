# bot/handlers/admin_prompt.py
import html
import json
import logging
from typing import Any, Dict, List, Set

from aiogram import Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from ..ai.prompt_optimizer_from_dataset import optimize_prompt_from_dataset
from ..config import Settings

logger = logging.getLogger(__name__)

ADMIN_IDS = {1305675046}
PROMPT_DEBUG_CHAT_ID = -5030824970


def _build_prompt_diff_payload(
        old_config: Dict[str, Any],
        new_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Eski va yangi prompt_config orasidagi farqni tayyorlaydi:
    - changed_rules: faqat o'zgargan rules bo'limlari
    - new_examples: eski configda bo'lmagan misollar
    """
    old_rules = (old_config.get("rules") or {}) if isinstance(old_config, dict) else {}
    new_rules = (new_config.get("rules") or {}) if isinstance(new_config, dict) else {}

    changed_rules: Dict[str, Dict[str, List[str]]] = {}

    for section, new_list in new_rules.items():
        old_list = old_rules.get(section, [])
        # Listlar farq qilsa – bu bo'limni o'zgargan deb olamiz
        if new_list != old_list:
            changed_rules[section] = {
                "old": old_list,
                "new": new_list,
            }

    # Examples bo'yicha: input bo'yicha yangi misollarni topamiz
    old_examples = old_config.get("examples") or []
    new_examples = new_config.get("examples") or []

    old_inputs: Set[str] = set()
    for ex in old_examples:
        if isinstance(ex, dict):
            inp = ex.get("input")
            if isinstance(inp, str):
                old_inputs.add(inp)

    new_examples_only: List[Dict[str, Any]] = []
    for ex in new_examples:
        if not isinstance(ex, dict):
            continue
        inp = ex.get("input")
        if isinstance(inp, str) and inp not in old_inputs:
            new_examples_only.append(ex)

    # Agar hech narsa o'zgarmagan bo'lsa ham strukturani qaytaramiz
    return {
        "changed_rules": changed_rules,
        "new_examples": new_examples_only,
    }


# bot/handlers/admin_prompt.py


def register_admin_prompt_handlers(dp: Dispatcher, settings: Settings) -> None:
    @dp.message(Command("optimize_prompt"), F.from_user.id.in_(ADMIN_IDS))
    async def cmd_optimize_prompt(message: Message):
        logger.info(
            "Admin optimize_prompt: chat=%s from=%s(%s)",
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
        )

        await message.answer("♻️ Prompt optimizatsiya qilinyapti...")

        try:
            result = optimize_prompt_from_dataset(
                settings=settings,
                limit=300,
            )
            old_config = result.get("old_config") or {}
            new_config = result.get("new_config") or {}

            await message.answer("✅ prompt_config.json yangilandi.")

            try:
                diff_payload = _build_prompt_diff_payload(old_config, new_config)

                changed_rules = diff_payload["changed_rules"]
                new_examples = diff_payload["new_examples"]

                if not changed_rules and not new_examples:
                    await message.bot.send_message(
                        chat_id=PROMPT_DEBUG_CHAT_ID,
                        text=(
                            "ℹ️ /optimize_prompt ishga tushdi, "
                            "lekin rules/examples'da sezilarli o'zgarish yo'q."
                        ),
                    )
                    return

                # --- QISQA IZOHLAR BLOKI ---
                changed_sections_list = list(changed_rules.keys())
                changed_sections_str = (
                    ", ".join(changed_sections_list) if changed_sections_list else "—"
                )
                new_examples_count = len(new_examples)

                reason_text = (
                    "<b>Qisqa izoh:</b>\n"
                    f"- O'zgargan rules bo'limlari: {html.escape(changed_sections_str)}\n"
                    f"- Yangi misollar soni: {new_examples_count}\n"
                    f"- Optimizatsiya manbasi: ai_orders/ai_order_dataset jadvalidagi "
                    "oxirgi 300 ta zakaz.\n"
                    "- Asosiy maqsad: telefon raqam va summani aniqlashdagi xatolarni "
                    "kamaytirish, chalkash so'zlarni (masalan, 'to'qsonlik', 'birlik' va h.k.) "
                    "telefon/summa deb noto'g'ri ushlamaslik."
                )

                # Diff JSON sifatida
                config_str = json.dumps(diff_payload, ensure_ascii=False, indent=2)
                if len(config_str) > 3500:
                    config_str_short = config_str[:3400] + "\n...\n(truncated)"
                else:
                    config_str_short = config_str

                text = (
                        "<b>🧠 Yangi prompt o'zgarishlari</b>\n"
                        "<i>(optimizer orqali yangilandi)</i>\n\n"
                        f"{reason_text}\n\n"
                        "<b>Diff (faqat yangi/yangilangan qism):</b>\n"
                        "<pre>" + html.escape(config_str_short) + "</pre>"
                )

                await message.bot.send_message(
                    chat_id=PROMPT_DEBUG_CHAT_ID,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.exception(
                    "Yangi prompt diff ni guruhga yuborishda xatolik: %s", e
                )

        except Exception as e:
            logger.exception("Prompt optimizatsiyada xatolik: %s", e)
            short_err = str(e)
            if len(short_err) > 500:
                short_err = short_err[:500] + " ..."
            await message.answer(
                "❌ Prompt optimizatsiyada xatolik yuz berdi.\n"
                "Detal uchun server logini ko'ring.\n\n"
                f"{short_err}"
            )
