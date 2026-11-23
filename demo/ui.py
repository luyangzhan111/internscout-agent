"""Shared presentation only; untrusted job strings are always escaped."""

from html import escape
from pathlib import Path

import streamlit as st


def install_design_system() -> None:
    css = (Path(__file__).parent / "assets" / "theme.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown(
        '<header class="is-brand"><div class="is-brand-main">'
        '<span class="is-logo" aria-hidden="true">'
        '<svg viewBox="0 0 32 32" fill="none"><path d="M23 9 18 22 9 23 14 10Z" '
        'stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>'
        '<circle cx="16" cy="16" r="2" fill="currentColor"/></svg></span>'
        '<div><div class="is-brand-name">InternScout<span> / </span></div>'
        '<div class="is-brand-caption">让每一次投递，更有依据</div></div></div>'
        '<span class="is-brand-note">你的求职工作台</span></header>',
        unsafe_allow_html=True,
    )


def page_heading(eyebrow: str, title: str, description: str) -> None:
    st.markdown(
        f'<section class="is-page-heading"><div class="is-eyebrow">{escape(eyebrow)}</div>'
        f'<h1>{escape(title)}</h1><p>{escape(description)}</p></section>',
        unsafe_allow_html=True,
    )


def job_heading(title: str, company: str, city: str, salary: str | None = None, rank: int | None = None) -> None:
    meta = " · ".join(value for value in (company, city, salary) if value)
    rank_text = f'<span class="is-rank">{rank:02d}</span>' if rank is not None else ""
    st.markdown(
        '<div class="is-job-heading">'
        f'<span class="is-company-icon" aria-hidden="true">{escape(company[:1] or "职")}</span>'
        f'<div class="is-job-copy"><h3>{escape(title)}</h3><p>{escape(meta)}</p></div>{rank_text}</div>',
        unsafe_allow_html=True,
    )


def badges(items: list[tuple[str, str]]) -> None:
    tones = {"neutral", "green", "amber", "red", "blue"}
    labels = "".join(
        f'<span class="is-badge is-badge-{tone if tone in tones else "neutral"}">{escape(label)}</span>'
        for label, tone in items
    )
    st.markdown(f'<div class="is-badges">{labels}</div>', unsafe_allow_html=True)


def summary_strip(items: list[tuple[str, str]]) -> None:
    content = "".join(
        f'<div class="is-stat"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>'
        for label, value in items
    )
    st.markdown(f'<div class="is-summary">{content}</div>', unsafe_allow_html=True)


def info_item(label: str, text: str, detail: str = "") -> None:
    """A compact text-only item; rule reasons may contain quoted job strings."""
    st.markdown(
        '<div class="is-info-item">'
        f'<strong>{escape(label)}</strong><p>{escape(text)}</p>'
        f'<small>{escape(detail)}</small></div>',
        unsafe_allow_html=True,
    )
