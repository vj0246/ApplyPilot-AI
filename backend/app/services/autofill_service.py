"""
autofill_service.py
--------------------
Paste a Google Form link, get it filled in. This never clicks submit —
it fills every field with an AI-generated answer, screenshots the result,
and stops. You open the real form and submit it yourself.

That's the actual design, not a missing feature: Google flags fill+submit
bots as spam, a bad AI answer deserves a human glance before it goes out,
and if something here goes wrong the blast radius is "you notice and fix
it" instead of "a recruiter already has it."

Playwright drives a real headless Chromium and reads the page DOM the way
a person's browser would. Google Forms structures each question as a
`<div role="listitem">` — we scrape that, send the questions through the
same answer_form_questions() the manual form-filler tab uses, then type/
click the answers into the live page.
"""
import asyncio
import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from app.services import ai_service

log = logging.getLogger(__name__)


@dataclass
class FormField:
    index: int
    question: str
    field_type: str   # text | paragraph | radio | checkbox | dropdown
    options: List[str] = field(default_factory=list)
    required: bool = False


@dataclass
class FilledField:
    index: int
    question: str
    answer: str
    field_type: str
    confidence: str = "medium"   # high | medium | low


def is_google_form_url(url: str) -> bool:
    return "docs.google.com/forms" in url


# ── Step 1: scrape questions off the live page ──────────────────────────
# Google doesn't publish a structure API, so this leans on role attributes
# (role=listitem / role=radio / role=checkbox) — the assumption that
# breaks first if Google ships a big redesign.

async def scrape_google_form(page: Page) -> Dict[str, Any]:
    title = ""
    try:
        title_el = await page.query_selector("div[role='heading'][aria-level='1']")
        if title_el:
            title = (await title_el.inner_text()).strip()
    except Exception:
        pass

    items = await page.query_selector_all("div[role='listitem']")
    fields: List[FormField] = []

    for idx, item in enumerate(items):
        try:
            field_data = await _read_single_question(item, idx)
            if field_data:
                fields.append(field_data)
        except Exception as e:
            log.warning(f"Couldn't parse form item {idx}: {e}")
            continue

    return {"title": title, "fields": fields}


async def _read_single_question(item, idx: int) -> Optional[FormField]:
    heading = await item.query_selector("div[role='heading']")
    if not heading:
        return None
    question_text = (await heading.inner_text()).strip()
    if not question_text:
        return None

    required = question_text.rstrip().endswith("*")
    question_text = question_text.rstrip("*").strip()

    radio_inputs = await item.query_selector_all("[role='radio']")
    if radio_inputs:
        options = [lbl.strip() for r in radio_inputs if (lbl := await r.get_attribute("aria-label"))]
        return FormField(idx, question_text, "radio", options, required)

    checkbox_inputs = await item.query_selector_all("[role='checkbox']")
    if checkbox_inputs:
        options = [lbl.strip() for c in checkbox_inputs if (lbl := await c.get_attribute("aria-label"))]
        return FormField(idx, question_text, "checkbox", options, required)

    listbox = await item.query_selector("[role='listbox']")
    if listbox:
        options = await _read_dropdown_options(listbox)
        return FormField(idx, question_text, "dropdown", options, required)

    textarea = await item.query_selector("textarea")
    if textarea:
        return FormField(idx, question_text, "paragraph", [], required)

    text_input = await item.query_selector("input[type='text']")
    if text_input:
        return FormField(idx, question_text, "text", [], required)

    # file upload, date picker, linear scale etc — skip rather than guess
    return None


async def _read_dropdown_options(listbox) -> List[str]:
    try:
        await listbox.click()
        await asyncio.sleep(0.3)
        opts = await listbox.query_selector_all("[role='option']")
        labels = [t.strip() for o in opts if (t := await o.inner_text()) and t.strip().lower() != "choose"]
        await listbox.page.keyboard.press("Escape")
        await asyncio.sleep(0.2)
        return labels
    except Exception:
        return []


# ── Step 2: get answers from the same AI function the manual form ───────
# filler tab uses — choice-based fields get their real options baked into
# the question text so Groq picks from what's actually on the page.

async def get_answers_for_fields(
    fields: List[FormField],
    resume_parsed: Dict,
    job_parsed: Optional[Dict],
    extra_context: str = "",
) -> List[FilledField]:
    questions_for_ai = []
    for f in fields:
        if f.options:
            opts = " / ".join(f.options)
            if f.field_type == "checkbox":
                questions_for_ai.append(f"{f.question} (choose one or more of: {opts})")
            else:
                questions_for_ai.append(f"{f.question} (choose exactly one of: {opts})")
        else:
            questions_for_ai.append(f.question)

    raw_answers = await ai_service.answer_form_questions(
        questions=questions_for_ai,
        resume_parsed=resume_parsed,
        job_parsed=job_parsed,
        extra_context=extra_context,
    )

    filled: List[FilledField] = []
    for f, raw in zip(fields, raw_answers):
        answer_text = raw.get("answer", "").strip()

        if f.field_type in ("radio", "dropdown") and f.options:
            matched = _match_option(answer_text, f.options)
            filled.append(FilledField(f.index, f.question, matched or f.options[0],
                                       f.field_type, confidence="high" if matched else "low"))
        elif f.field_type == "checkbox" and f.options:
            matched_list = _match_multiple_options(answer_text, f.options)
            filled.append(FilledField(f.index, f.question, ", ".join(matched_list),
                                       f.field_type, confidence="high" if matched_list else "low"))
        else:
            filled.append(FilledField(f.index, f.question, answer_text, f.field_type, confidence="medium"))

    return filled


def _match_option(answer: str, options: List[str]) -> Optional[str]:
    # Groq paraphrases options sometimes ("Yes" vs "Yes, I am") — exact
    # match first, loose substring match second.
    # Guard: "" is a substring of every string in Python, so an empty
    # answer would incorrectly match the first option without this check.
    answer_l = answer.lower().strip()
    if not answer_l or not options:
        return None
    for opt in options:
        if opt.lower().strip() == answer_l:
            return opt
    for opt in options:
        if opt.lower() in answer_l or answer_l in opt.lower():
            return opt
    return None


def _match_multiple_options(answer: str, options: List[str]) -> List[str]:
    parts = re.split(r",|;|\band\b", answer, flags=re.I)
    matched = []
    for part in parts:
        m = _match_option(part.strip(), options)
        if m and m not in matched:
            matched.append(m)
    return matched


# ── Step 3: type/click answers into the real page ────────────────────────

async def fill_google_form(page: Page, filled_fields: List[FilledField]) -> None:
    items = await page.query_selector_all("div[role='listitem']")

    for ff in filled_fields:
        if ff.index >= len(items) or not ff.answer:
            continue
        item = items[ff.index]
        try:
            if ff.field_type == "text":
                inp = await item.query_selector("input[type='text']")
                if inp:
                    await inp.click()
                    await inp.fill(ff.answer)

            elif ff.field_type == "paragraph":
                ta = await item.query_selector("textarea")
                if ta:
                    await ta.click()
                    await ta.fill(ff.answer)

            elif ff.field_type == "radio":
                radios = await item.query_selector_all("[role='radio']")
                for r in radios:
                    label = await r.get_attribute("aria-label")
                    if label and label.strip() == ff.answer:
                        await r.click()
                        break

            elif ff.field_type == "checkbox":
                chosen = [a.strip() for a in ff.answer.split(",") if a.strip()]
                boxes = await item.query_selector_all("[role='checkbox']")
                for b in boxes:
                    label = await b.get_attribute("aria-label")
                    if label and label.strip() in chosen:
                        await b.click()

            elif ff.field_type == "dropdown":
                listbox = await item.query_selector("[role='listbox']")
                if listbox:
                    await listbox.click()
                    await asyncio.sleep(0.3)
                    opts = await listbox.query_selector_all("[role='option']")
                    found = False
                    for o in opts:
                        t = (await o.inner_text()).strip()
                        if t == ff.answer:
                            await o.click()
                            found = True
                            break
                    if not found:
                        await page.keyboard.press("Escape")

            # small pause between fields — Forms' client-side validation
            # doesn't love 20 fields changing in the same tick
            await asyncio.sleep(0.25)

        except Exception as e:
            log.warning(f"Couldn't fill field {ff.index} ({ff.question[:40]}): {e}")
            continue


# ── Orchestration ─────────────────────────────────────────────────────────

async def run_autofill(
    form_url: str,
    resume_parsed: Dict,
    job_parsed: Optional[Dict],
    extra_context: str = "",
) -> Dict[str, Any]:
    if not is_google_form_url(form_url):
        raise ValueError("That doesn't look like a Google Forms URL (expected docs.google.com/forms/...)")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 1600})

            try:
                await page.goto(form_url, wait_until="networkidle", timeout=20000)
            except PlaywrightTimeout:
                raise ValueError("The form took too long to load. Check the link and try again.")

            no_responses = await page.query_selector("text=no longer accepting responses")
            if no_responses:
                raise ValueError("This form is no longer accepting responses.")

            scraped = await scrape_google_form(page)
            fields: List[FormField] = scraped["fields"]

            if not fields:
                raise ValueError(
                    "Couldn't find any fillable questions on this form. "
                    "It might be using a layout this tool doesn't recognize yet."
                )

            filled = await get_answers_for_fields(fields, resume_parsed, job_parsed, extra_context)
            await fill_google_form(page, filled)

            await asyncio.sleep(0.5)
            screenshot_bytes = await page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

            unfilled = sum(1 for f in filled if not f.answer)

            return {
                "title": scraped["title"],
                "form_url": form_url,
                "fields": [
                    {"question": f.question, "field_type": f.field_type,
                     "answer": f.answer, "confidence": f.confidence}
                    for f in filled
                ],
                "unfilled_count": unfilled,
                "screenshot_base64": screenshot_b64,
            }

        finally:
            # close even on error — a leaked headless Chromium process
            # quietly eats server memory over time
            await browser.close()
