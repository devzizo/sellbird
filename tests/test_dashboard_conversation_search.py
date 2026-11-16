"""The Conversations search box and the "Review in Outbox" button."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import sellbird.dashboard as dash

APP_JS = (Path(dash.__file__).parent / "web" / "app.js").read_text(encoding="utf-8")


def _func(name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^}}\n", APP_JS, re.S | re.M)
    assert match, name
    return match.group(0)


def _matches(convo: dict, query: str) -> bool:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = _func("convoMatches") + \
        f"\nprocess.stdout.write(String(convoMatches({json.dumps(convo)}, {json.dumps(query)})));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True,
                         check=True, timeout=30).stdout
    return out == "true"


CONVO = {
    "first_name": "Elena", "last_name": "Park", "company": "Harbor Dental Studio",
    "prospect_email": "elena@harbor.test", "intent": "interested", "status": "open",
    "emails": [{"subject": "Booking at Harbor", "body": "Saw you take calls only."}],
    "thread": [{"sender": "prospect", "content": "Sounds useful, what does it cost?"}],
    "draft": {"id": "ob1", "subject": "Re: Booking at Harbor", "body": "Pricing starts at a flat fee."},
}


@pytest.mark.parametrize("query", [
    "", "  ", "elena", "PARK", "harbor dental", "elena@harbor.test",
    "what does it cost", "flat fee", "calls only", "interested",
])
def test_search_finds_every_part_of_a_conversation(query):
    assert _matches(CONVO, query)


@pytest.mark.parametrize("query", ["roofing", "elena roofing"])
def test_every_word_must_match(query):
    assert not _matches(CONVO, query)


def test_search_survives_missing_fields():
    assert _matches({"company": "Highline Roofing"}, "roofing")
    assert not _matches({}, "roofing")


def test_review_in_outbox_opens_that_draft():
    card = _func("convoCard")
    assert "reviewDraft(' + jsq(c.draft.id) + ')" in card
    assert "goTab(\\'outbox\\')" not in card
    assert "_desk.focus" in _func("paintOutbox")


def _outbox_matches(item: dict, query: str) -> bool:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = _func("outboxMatches") + \
        f"\nprocess.stdout.write(String(outboxMatches({json.dumps(item)}, {json.dumps(query)})));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True,
                         check=True, timeout=30).stdout
    return out == "true"


DRAFT = {
    "to_email": "priya@highline.test", "subject": "Roof leads", "body": "Saw you're hiring a dispatcher.",
    "kind": "reply", "error": "held for your review: links to a new site",
    "context": {"company": "Highline Roofing", "contact": "Priya Nair", "campaign": "Phoenix HVAC"},
}


@pytest.mark.parametrize("query", [
    "", "priya@highline", "roof leads", "DISPATCHER", "highline roofing", "priya nair",
    "phoenix", "held", "reply",
])
def test_outbox_search_finds_every_part_of_an_email(query):
    assert _outbox_matches(DRAFT, query)


@pytest.mark.parametrize("query", ["dental", "priya dental"])
def test_outbox_search_needs_every_word(query):
    assert not _outbox_matches(DRAFT, query)


def test_outbox_search_rows_without_context():
    assert _outbox_matches({"to_email": "x@harbor.test", "subject": "old"}, "harbor")


def test_approve_all_is_hidden_while_searching():
    paint = _func("paintOutbox")
    assert "!searching" in paint
    assert "_outboxQuery = ''" in _func("reviewDraft")
