"""Product-area themes for CEO reporting — understanding, not ticket titles."""

from __future__ import annotations

import re

from app.models import Ticket
from app.services.ticket_parser import infer_module_affected

THEME_RULES: list[tuple[str, str, re.Pattern]] = [
    (
        "Customer Concerns (AI)",
        "Concern sync, work order updates, Arabic/localisation, payload handling",
        re.compile(
            r"customer concern|work\s*order|workorder|arabic|concern.*not|not reflect|"
            r"not updat|not getting|cep|gms|motrex|payload",
            re.I,
        ),
    ),
    (
        "Invoice & billing",
        "Invoice numbers, sequences, tax/GST, amounts, Zoho sync",
        re.compile(
            r"invoice number|invoice.*generat|sequence|gst|tax|amount mismatch|billing|zoho",
            re.I,
        ),
    ),
    (
        "Job Card",
        "Open/close, status, inward, parts and vehicle on job card",
        re.compile(r"job card|jobcard|close job|open job|inward", re.I),
    ),
    (
        "Reports",
        "Report loading, sales register, HSN, offline sync",
        re.compile(r"report|sales register|hsn|offline.*sync|logout", re.I),
    ),
    (
        "Notifications",
        "WhatsApp, email, SMS delivery",
        re.compile(r"whatsapp|notification|email.*not|sms|otp|deliver", re.I),
    ),
    (
        "PDF & print",
        "PDF generation and print layout",
        re.compile(r"\bpdf\b|print|stamp|render", re.I),
    ),
    (
        "Stock & parts",
        "Stock, bulk upload, parts inward, master data",
        re.compile(r"stock|parts inward|bulk upload|master.*part", re.I),
    ),
    (
        "Performance",
        "Slow loading, hangs, timeouts",
        re.compile(r"slow|performance|lag|hang|loading|timeout", re.I),
    ),
    (
        "UI & display",
        "Screens, buttons, layout, visibility",
        re.compile(r"display|screen|button|layout|visible|blank|ui ", re.I),
    ),
    (
        "Integration & API",
        "External sync and API failures",
        re.compile(r"integration|api|sync fail|webhook", re.I),
    ),
]


def classify_product_area(ticket: Ticket) -> str:
    text = f"{ticket.title or ''} {ticket.description or ''}"
    mod = infer_module_affected(ticket.title or "", ticket.description or "")
    combined = f"{mod} {text}"
    for name, _, pat in THEME_RULES:
        if pat.search(combined):
            return name
    return "Other"


def area_description(name: str) -> str:
    for n, desc, _ in THEME_RULES:
        if n == name:
            return desc
    return "Cross-cutting defects"


def classify_text_area(text: str, modules: list[str] | None = None) -> str:
    combined = f"{' '.join(modules or [])} {text}"
    for name, _, pat in THEME_RULES:
        if pat.search(combined):
            return name
    return "Other"
