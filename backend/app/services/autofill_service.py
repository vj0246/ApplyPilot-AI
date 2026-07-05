"""
autofill_service.py
--------------------
Paste a Google Form or a Microsoft Form link, get it filled in. This never
clicks submit — it fills every field with an AI-generated answer,
screenshots the result, and stops. You open the real form and submit it
yourself.

That's the actual design, not a missing feature: both providers flag
fill+submit bots as spam, a bad AI answer deserves a human glance before
it goes out, and if something here goes wrong the blast radius is "you
notice and fix it" instead of "a recruiter already has it."

Playwright drives a real headless Chromium and reads the page DOM the way
a person's browser would. Google Forms structures each question as a
`<div role="listitem">`; Microsoft Forms leans on the same kind of ARIA
roles (radiogroup, radio, checkbox, listbox) inside a question container,
so both scrapers read role attributes rather than CSS class names, which
break the moment either provider ships a redesign. Both providers send
the scraped questions through the same answer_form_questions() the manual
form filler tab uses, then type/click the answers into the live page.
"""
import asyncio
import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

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
    entry_id: Optional[str] = None


@dataclass
class FilledField:
    index: int
    question: str
    answer: str
    field_type: str
    confidence: str = "medium"   # high | medium | low


class FormScrapeError(ValueError):
    """Raised when the page loaded but no fillable questions were found on
    it. Carries a screenshot of whatever Playwright actually saw, because
    the two real causes look identical from the error message alone: an
    unrecognized form layout, or Google/Microsoft showing a bot check
    instead of the real form to a cloud server's IP address. Without the
    screenshot there is no way to tell which one happened from server
    logs alone."""
    def __init__(self, message: str, screenshot_b64: Optional[str] = None):
        super().__init__(message)
        self.screenshot_b64 = screenshot_b64


def is_google_form_url(url: str) -> bool:
    return "docs.google.com/forms" in url


def is_microsoft_form_url(url: str) -> bool:
    return "forms.office.com" in url or "forms.microsoft.com" in url or "forms.office365.com" in url


def is_supported_form_url(url: str) -> bool:
    return is_google_form_url(url) or is_microsoft_form_url(url)


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
    entry_id = await _read_entry_id(item)

    radio_inputs = await item.query_selector_all("[role='radio']")
    if radio_inputs:
        options = [lbl.strip() for r in radio_inputs if (lbl := await r.get_attribute("aria-label"))]
        if _looks_like_grid(options):
            # A multiple choice grid (one row of radio buttons per skill,
            # columns like Beginner/Intermediate/Expert) renders each cell
            # as its own [role='radio'] with an aria-label like "Python,
            # response for Beginner" — every cell across every row lands
            # in this one query, so what looks like a normal single choice
            # question is actually N unrelated questions tangled together,
            # and the id captured above belongs to internal grid plumbing,
            # not a single answerable entry. There's no correct single
            # answer to give this, so it's left for the person to fill in.
            return None
        return FormField(idx, question_text, "radio", options, required, entry_id)

    checkbox_inputs = await item.query_selector_all("[role='checkbox']")
    if checkbox_inputs:
        options = [lbl.strip() for c in checkbox_inputs if (lbl := await c.get_attribute("aria-label"))]
        if _looks_like_grid(options):
            return None
        return FormField(idx, question_text, "checkbox", options, required, entry_id)

    listbox = await item.query_selector("[role='listbox']")
    if listbox:
        options = await _read_dropdown_options(listbox)
        return FormField(idx, question_text, "dropdown", options, required, entry_id)

    textarea = await item.query_selector("textarea")
    if textarea:
        return FormField(idx, question_text, "paragraph", [], required, entry_id)

    text_input = await item.query_selector("input[type='text']")
    if text_input:
        return FormField(idx, question_text, "text", [], required, entry_id)

    # file upload, date picker, linear scale etc — skip rather than guess
    return None


def _looks_like_grid(options: List[str]) -> bool:
    return any(", response for " in o for o in options)


async def _read_entry_id(item) -> Optional[str]:
    # When a field renders a real <input>/<textarea> whose name attribute
    # is literally "entry.<id>", that id is authoritative — it's the same
    # identifier Google's own formResponse endpoint reads on submit, and
    # the same one the "Get pre-filled link" feature encodes into a
    # shareable URL.
    # A real Google entry id is always a plain number. Some named inputs
    # carry a suffix used for internal plumbing (seen in the wild:
    # "entry.1677974547_sentinel" on a grid question) — appending that
    # suffix into a URL as entry.<id>_sentinel isn't a parameter Google's
    # prefill mechanism recognizes, and one invalid entry name is enough
    # to make it discard prefilling the entire page rather than just that
    # one field. Anything that isn't clean digits is rejected outright.
    named = await item.query_selector("input[name^='entry.'], textarea[name^='entry.']")
    if named:
        name = await named.get_attribute("name")
        if name and "." in name:
            candidate = name.split(".", 1)[1]
            if candidate.isdigit():
                return candidate

    # Most questions have no named input at all (Google renders custom
    # widgets), so the id comes from the data-params attribute on the
    # question container. Its structure is
    #   [<question id>, "Question text", ..., [[<entry id>, ...]]]
    # and the two ids are different numbers. Prefill only accepts the
    # NESTED one after the double bracket — verified live: with the
    # nested id the form loads with the value typed in, with the first
    # number Google ignores the parameter and shows a blank form. The
    # old code here grabbed the first number, which is why every
    # "pre-filled" link opened empty.
    # data-params can sit on the listitem itself or on a nested element
    # depending on which question type rendered it, so check both rather
    # than assuming one exact spot in the tree.
    params = await item.get_attribute("data-params")
    if not params:
        holder = await item.query_selector("[data-params]")
        if holder:
            params = await holder.get_attribute("data-params")
    if params:
        m = re.search(r"\[\[(\d{3,})", params)
        if m:
            return m.group(1)

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
    knowledge_graph: Optional[Dict] = None,
    custom_instructions: str = "",
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
        knowledge_graph=knowledge_graph,
        custom_instructions=custom_instructions,
    )

    filled: List[FilledField] = []
    for f, raw in zip(fields, raw_answers):
        answer_text = raw.get("answer", "").strip()

        if f.field_type in ("radio", "dropdown", "checkbox") and not f.options:
            # Scraping found the widget but couldn't read its option list —
            # a free-text sentence has nowhere valid to go on a constrained
            # field type, and typing one into a dropdown or radio group
            # either fails outright or corrupts the pre-filled link with a
            # value Google was never going to accept. Left for the person
            # to pick by hand instead of guessing.
            filled.append(FilledField(f.index, f.question, "", f.field_type, confidence="low"))
        elif f.field_type in ("radio", "dropdown"):
            matched = _match_option(answer_text, f.options)
            filled.append(FilledField(f.index, f.question, matched or f.options[0],
                                       f.field_type, confidence="high" if matched else "low"))
        elif f.field_type == "checkbox":
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


# ── Microsoft Forms: scrape and fill ─────────────────────────────────────
# Microsoft Forms does not publish a structure API either, so this leans on
# the same accessibility roles a screen reader would use: each question
# sits in a container we can find by role="group" or a data automation id,
# with role="radiogroup" plus role="radio" children for single choice,
# role="group" plus role="checkbox" children for multiple choice, and a
# plain textarea or text input otherwise. The first thing to break if
# Microsoft ships a redesign is this role mapping, same trade as the
# Google Forms scraper above.

async def scrape_microsoft_form(page: Page) -> Dict[str, Any]:
    title = ""
    try:
        title_el = await page.query_selector("h1")
        if title_el:
            title = (await title_el.inner_text()).strip()
    except Exception:
        pass

    items = await page.query_selector_all("div[data-automation-id='questionItem'], div[role='group']")
    fields: List[FormField] = []
    seen_questions = set()

    for idx, item in enumerate(items):
        try:
            field_data = await _read_single_ms_question(item, idx)
            if field_data and field_data.question not in seen_questions:
                fields.append(field_data)
                seen_questions.add(field_data.question)
        except Exception as e:
            log.warning(f"Couldn't parse Microsoft Form item {idx}: {e}")
            continue

    return {"title": title, "fields": fields}


async def _read_single_ms_question(item, idx: int) -> Optional[FormField]:
    heading = await item.query_selector("[role='heading'], .text-format-content, label")
    if not heading:
        return None
    question_text = (await heading.inner_text()).strip()
    if not question_text:
        return None

    required = "*" in question_text[-2:]
    question_text = question_text.rstrip("*").strip()

    radiogroup = await item.query_selector("[role='radiogroup']")
    if radiogroup:
        radios = await radiogroup.query_selector_all("[role='radio']")
        options = [lbl.strip() for r in radios if (lbl := await r.get_attribute("aria-label") or await r.inner_text())]
        if options:
            return FormField(idx, question_text, "radio", options, required)

    checkboxes = await item.query_selector_all("[role='checkbox']")
    if checkboxes:
        options = [lbl.strip() for c in checkboxes if (lbl := await c.get_attribute("aria-label") or await c.inner_text())]
        if options:
            return FormField(idx, question_text, "checkbox", options, required)

    listbox = await item.query_selector("[role='listbox'], select")
    if listbox:
        options = await _read_dropdown_options(listbox)
        return FormField(idx, question_text, "dropdown", options, required)

    textarea = await item.query_selector("textarea")
    if textarea:
        return FormField(idx, question_text, "paragraph", [], required)

    text_input = await item.query_selector("input[type='text']")
    if text_input:
        return FormField(idx, question_text, "text", [], required)

    # file upload, date picker, rating scale etc — skip rather than guess
    return None


async def fill_microsoft_form(page: Page, filled_fields: List[FilledField]) -> None:
    items = await page.query_selector_all("div[data-automation-id='questionItem'], div[role='group']")

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
                    label = (await r.get_attribute("aria-label")) or (await r.inner_text())
                    if label and label.strip() == ff.answer:
                        await r.click()
                        break

            elif ff.field_type == "checkbox":
                chosen = [a.strip() for a in ff.answer.split(",") if a.strip()]
                boxes = await item.query_selector_all("[role='checkbox']")
                for b in boxes:
                    label = (await b.get_attribute("aria-label")) or (await b.inner_text())
                    if label and label.strip() in chosen:
                        await b.click()

            elif ff.field_type == "dropdown":
                listbox = await item.query_selector("[role='listbox'], select")
                if listbox:
                    await listbox.click()
                    await asyncio.sleep(0.3)
                    opts = await listbox.query_selector_all("[role='option'], option")
                    found = False
                    for o in opts:
                        t = (await o.inner_text()).strip()
                        if t == ff.answer:
                            await o.click()
                            found = True
                            break
                    if not found:
                        await page.keyboard.press("Escape")

            # small pause between fields, same reasoning as the Google Forms
            # filler: client-side validation does not love many fields
            # changing in the same tick
            await asyncio.sleep(0.25)

        except Exception as e:
            log.warning(f"Couldn't fill Microsoft Form field {ff.index} ({ff.question[:40]}): {e}")
            continue


# ── Pre-filled link ───────────────────────────────────────────────────────
# The same mechanism behind Google Forms' own "Get pre-filled link" feature:
# encode each answer as an entry.<id>=value query parameter on the viewform
# URL. Opening that URL shows the form with those answers already typed in,
# still fully editable, so the person reviews and clicks submit inside the
# real Google Forms page instead of a link that reloads it blank. A field
# with no captured entry id (extraction failed, or it's a type this tool
# doesn't map, such as file upload) is simply left out — nothing to prefill
# there, the person fills that one in by hand same as always.

def build_prefilled_url(form_url: str, form_fields: List[FormField], filled: List[FilledField]) -> Optional[str]:
    entry_by_index = {f.index: f.entry_id for f in form_fields}
    params: List[tuple] = []

    for ff in filled:
        entry_id = entry_by_index.get(ff.index)
        if not entry_id or not ff.answer:
            continue
        if ff.field_type == "checkbox":
            for value in [v.strip() for v in ff.answer.split(",") if v.strip()]:
                params.append((f"entry.{entry_id}", value))
        else:
            params.append((f"entry.{entry_id}", ff.answer))

    if not params:
        return None

    split = urlsplit(form_url)
    existing = parse_qsl(split.query, keep_blank_values=True)
    combined = existing + params
    new_query = urlencode(combined, doseq=False)
    return urlunsplit((split.scheme, split.netloc, split.path, new_query, split.fragment))


# ── Orchestration ─────────────────────────────────────────────────────────

async def run_autofill(
    form_url: str,
    resume_parsed: Dict,
    job_parsed: Optional[Dict],
    extra_context: str = "",
    knowledge_graph: Optional[Dict] = None,
    custom_instructions: str = "",
) -> Dict[str, Any]:
    is_google = is_google_form_url(form_url)
    is_microsoft = is_microsoft_form_url(form_url)
    if not is_google and not is_microsoft:
        raise ValueError(
            "That doesn't look like a Google Forms or Microsoft Forms link "
            "(expected a docs.google.com/forms/... or forms.office.com/... URL)."
        )

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

            # Some forms are set to "restrict to users in an organization" or
            # otherwise require a signed-in Google account before showing any
            # question at all — Google serves its own accounts.google.com
            # sign-in page instead of the form. That is enforced by Google on
            # its own servers, tied to whether the request carries a session
            # for an authorized account; no amount of DOM scraping gets past
            # it, and this tool will never store or replay someone's real
            # Google login to try. Detecting it up front gives a clear
            # answer instead of the generic "no fields found" message.
            if is_google and "accounts.google.com" in page.url:
                raise ValueError(
                    "This form requires the person filling it out to be signed in to an authorized "
                    "Google account before it will even show its questions. That is a restriction "
                    "Google enforces on its own servers, and no automated tool can fill a form it is "
                    "never shown. If this is your own form, turn off \"Restrict to users in your "
                    "organization\" or the sign in requirement under Settings, then Responses. "
                    "Otherwise, ask whoever owns the form for a link that does not require signing in."
                )

            scraped = await scrape_google_form(page) if is_google else await scrape_microsoft_form(page)
            fields: List[FormField] = scraped["fields"]

            if not fields:
                debug_bytes = await page.screenshot(full_page=True)
                debug_b64 = base64.b64encode(debug_bytes).decode()
                raise FormScrapeError(
                    "Couldn't find any fillable questions on this form. This usually means either "
                    "the form uses a layout this tool doesn't recognize yet, or the form provider "
                    "showed a bot check instead of the real form because the request came from a "
                    "cloud server. Check the screenshot below to see what was actually loaded.",
                    screenshot_b64=debug_b64,
                )

            filled = await get_answers_for_fields(
                fields, resume_parsed, job_parsed, extra_context, knowledge_graph,
                custom_instructions,
            )
            if is_google:
                await fill_google_form(page, filled)
            else:
                await fill_microsoft_form(page, filled)

            await asyncio.sleep(0.5)
            screenshot_bytes = await page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

            unfilled = sum(1 for f in filled if not f.answer)

            # Google Forms only — Microsoft Forms has no equivalent
            # pre-filled link mechanism, so that flow keeps pointing at
            # the plain form_url as it always has.
            prefilled_url = build_prefilled_url(form_url, fields, filled) if is_google else None

            return {
                "title": scraped["title"],
                "form_url": form_url,
                "prefilled_url": prefilled_url,
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
