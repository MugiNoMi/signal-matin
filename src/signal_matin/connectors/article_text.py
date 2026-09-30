"""Texte d'un article à partir de sa page web, sans dépendance externe.

Garde les paragraphes du corps de l'article (balise <article> si elle existe,
sinon toute la page) et écarte les blocs trop courts : menus, légendes,
mentions. Les articles réservés aux abonnés ne livrent que leur début.
"""
from __future__ import annotations

import urllib.request
from html.parser import HTMLParser

_HEADERS = {
    "User-Agent": "Signal-Matin/1.0 (+https://github.com/sosoj92/signal-matin)",
    "Accept": "text/html,*/*",
}
_SKIP = {"script", "style", "noscript", "svg", "figure", "figcaption", "nav", "footer",
         "header", "aside", "form", "button"}


class _Paragraphs(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.article_depth = 0
        self.in_paragraph = False
        self.current: list[str] = []
        self.inside: list[str] = []   # paragraphes dans <article>
        self.anywhere: list[str] = []  # tous les paragraphes

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP:
            self.skip_depth += 1
        elif tag == "article":
            self.article_depth += 1
        elif tag == "p" and not self.skip_depth:
            self.in_paragraph, self.current = True, []

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "article" and self.article_depth:
            self.article_depth -= 1
        elif tag == "p" and self.in_paragraph:
            text = " ".join("".join(self.current).split())
            if text:
                self.anywhere.append(text)
                if self.article_depth:
                    self.inside.append(text)
            self.in_paragraph = False

    def handle_data(self, data: str) -> None:
        if self.in_paragraph and not self.skip_depth:
            self.current.append(data)


def extract_article_text(page: str, *, min_paragraph: int = 60, max_chars: int = 12000) -> str:
    parser = _Paragraphs()
    parser.feed(page)
    paragraphs = parser.inside if sum(map(len, parser.inside)) > 400 else parser.anywhere
    kept, total = [], 0
    for paragraph in paragraphs:
        if len(paragraph) < min_paragraph or paragraph in kept:
            continue
        kept.append(paragraph)
        total += len(paragraph)
        if total >= max_chars:
            break
    return "\n\n".join(kept)[:max_chars]


def fetch_article_text(url: str, *, timeout: int = 15) -> str:
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        page = response.read(3_000_000).decode(charset, errors="replace")
    return extract_article_text(page)
