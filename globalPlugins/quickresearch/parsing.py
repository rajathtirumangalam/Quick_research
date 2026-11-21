# -*- coding: UTF-8 -*-
# Research It - pure parsing helpers. No NVDA or network imports, so everything here is unit tested.

import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


class ResearchError(Exception):
	"""A failure the user should hear about. `kind` is mapped to a translated message by the UI."""

	def __init__(self, kind, **info):
		super().__init__(kind)
		self.kind = kind
		self.info = info


# ---------------------------------------------------------------- result document

class Doc:
	"""Results as headings, paragraphs and lists, renderable as HTML (results window) or plain text."""

	def __init__(self, title):
		self.title = title
		self.blocks = []  # (kind, payload, link)

	def heading(self, text, level=2):
		self.blocks.append(("h%d" % level, text, None))
		return self

	def para(self, text, link=None):
		self.blocks.append(("p", text, link))
		return self

	def items(self, texts):
		self.blocks.append(("ul", list(texts), None))
		return self

	def to_html(self):
		parts = []
		for kind, payload, link in self.blocks:
			if kind == "ul":
				parts.append("<ul>%s</ul>" % "".join("<li>%s</li>" % html.escape(t) for t in payload))
			elif kind == "p":
				text = html.escape(payload)
				if link:
					text = '<a href="%s">%s</a>' % (html.escape(link, quote=True), text)
				parts.append("<p>%s</p>" % text)
			else:
				parts.append("<%s>%s</%s>" % (kind, html.escape(payload), kind))
		return "\n".join(parts)

	def to_text(self):
		lines = []
		for kind, payload, _link in self.blocks:
			if kind == "ul":
				lines.extend("- %s" % item for item in payload)
			else:
				lines.append(payload)
			lines.append("")
		return "\n".join(lines).strip()

	def summary(self, limit=600):
		"""Short plain text for speaking: everything flattened, cut at a word boundary."""
		flat = []
		for kind, payload, _link in self.blocks:
			flat.extend(payload if kind == "ul" else [payload])
		text = " ".join(" ".join(flat).split())
		if len(text) <= limit:
			return text
		return text[:limit].rsplit(" ", 1)[0] + "..."


# ---------------------------------------------------------------- languages and scripts

# Unicode blocks of the Indian scripts the add-on can detect, mapped to a language code.
SCRIPTS = [
	("hi", 0x0900, 0x097F),  # Devanagari (Hindi, Marathi, Sanskrit, Nepali)
	("bn", 0x0980, 0x09FF),
	("pa", 0x0A00, 0x0A7F),  # Gurmukhi
	("gu", 0x0A80, 0x0AFF),
	("ta", 0x0B80, 0x0BFF),
	("te", 0x0C00, 0x0C7F),
	("kn", 0x0C80, 0x0CFF),
	("ml", 0x0D00, 0x0D7F),
]
WIKI_LANGUAGES = ["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"]

# Section titles used for each language on the English Wiktionary, in order of preference.
WIKTIONARY_SECTIONS = {
	"en": ["English"], "hi": ["Hindi", "Marathi", "Sanskrit", "Nepali"], "mr": ["Marathi", "Hindi", "Sanskrit"],
	"bn": ["Bengali"], "ta": ["Tamil"], "te": ["Telugu"], "gu": ["Gujarati"],
	"kn": ["Kannada"], "ml": ["Malayalam"], "pa": ["Punjabi"],
}


def detect_language(text):
	"""Language code for the dominant Indian script in the text, else 'en'."""
	counts = {}
	for char in text:
		code = ord(char)
		for lang, low, high in SCRIPTS:
			if low <= code <= high:
				counts[lang] = counts.get(lang, 0) + 1
				break
	if not counts:
		return "en"
	return max(sorted(counts), key=lambda lang: counts[lang])


# ---------------------------------------------------------------- dictionary (Wiktionary)

_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")
_KEEP_SECTION = re.compile(
	r"^(Etymology|Pronunciation|Noun|Proper noun|Verb|Adjective|Adverb|Pronoun|Preposition|Postposition|"
	r"Conjunction|Interjection|Determiner|Article|Numeral|Particle|Classifier|Participle|Phrase|Prefix|"
	r"Suffix|Symbol|Letter|Contraction|Initialism|Abbreviation|Acronym|Idiom|Proverb)( \d+)?$"
)


def _sections(extract):
	sections = []
	for line in extract.splitlines():
		match = _HEADING.match(line)
		if match:
			sections.append((len(match.group(1)), match.group(2), []))
		elif sections and line.strip():
			sections[-1][2].append(line.strip())
	return sections


def parse_wiktionary(extract, language_names):
	"""[(section title, [lines])] for the first language found, keeping only useful sections."""
	sections = _sections(extract)
	for name in language_names:
		for index, (level, title, _body) in enumerate(sections):
			if level == 2 and title == name:
				end = next((j for j in range(index + 1, len(sections)) if sections[j][0] == 2), len(sections))
				return [(t, body) for _l, t, body in sections[index + 1:end] if _KEEP_SECTION.match(t) and body]
	return []


# ---------------------------------------------------------------- currency

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
_CURRENCY_NAMES = {
    "us dollars": "USD", "us dollar": "USD", "american dollars": "USD",
    "american dollar": "USD", "dollars": "USD", "dollar": "USD",
    "canadian dollars": "CAD", "canadian dollar": "CAD",
    "australian dollars": "AUD", "australian dollar": "AUD",
    "singapore dollars": "SGD", "singapore dollar": "SGD",
    "indian rupees": "INR", "indian rupee": "INR", "rupees": "INR", "rupee": "INR",
    "euros": "EUR", "euro": "EUR",
    "british pounds": "GBP", "british pound": "GBP", "pounds": "GBP", "pound": "GBP",
    "japanese yen": "JPY", "yen": "JPY",
    "swiss francs": "CHF", "swiss franc": "CHF", "francs": "CHF", "franc": "CHF",
    "chinese yuan": "CNY", "yuan": "CNY", "renminbi": "CNY",
    "uae dirhams": "AED", "uae dirham": "AED", "dirhams": "AED", "dirham": "AED",
}
_CURRENCY = re.compile(
    r"^\s*(?:(\d[\d,]*(?:\.\d+)?|\.\d+)\s*)?([A-Za-z]{3})(?:\s*(?:to|in|into|->|=|:)?\s*([A-Za-z]{3}))?\s*$",
    re.IGNORECASE
)


def parse_currency(query, home=""):
    """Parse amounts and common currency names; an omitted amount means one unit."""
    text = (query or "").strip().lower()
    for name, code in sorted(_CURRENCY_NAMES.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", code, text)
    lead = re.match(r"^([$€£₹¥])\s*(\d[\d,]*(?:\.\d+)?|\.\d+)(.*)$", text)
    if lead:
        text = "%s %s%s" % (lead.group(2), CURRENCY_SYMBOLS[lead.group(1)], lead.group(3))
    for symbol, code in CURRENCY_SYMBOLS.items():
        text = text.replace(symbol, " %s " % code)
    text = " ".join(text.split())
    match = _CURRENCY.match(text)
    if not match:
        return None
    amount = float(match.group(1).replace(",", "")) if match.group(1) else 1.0
    source = match.group(2).upper()
    target = (match.group(3) or home or "").upper()
    if not target:
        return None
    return amount, source, target


def format_amount(value):
	return "{:,.2f}".format(value) if abs(value) >= 1 else "{:,.4f}".format(value)


# ---------------------------------------------------------------- JSON, feeds, HTML

def json_values(data, path):
	"""Values at a dotted path. Numbers index lists; '*' fans out over every item."""
	nodes = [data]
	for token in [t for t in path.split(".") if t]:
		next_nodes = []
		for node in nodes:
			if token == "*":
				next_nodes.extend(node if isinstance(node, list) else list(node.values()) if isinstance(node, dict) else [])
			elif isinstance(node, dict) and token in node:
				next_nodes.append(node[token])
			elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
				next_nodes.append(node[int(token)])
		nodes = next_nodes
	flat = []
	for node in nodes:
		if isinstance(node, (dict, list)):
			flat.append(json.dumps(node, ensure_ascii=False))
		elif node is not None:
			flat.append(str(node))
	return flat


class _TextExtractor(HTMLParser):
	_SKIP = {"script", "style", "noscript", "head", "svg", "template"}
	_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
		"ul", "ol", "table", "blockquote", "pre", "header", "footer"}

	def __init__(self):
		super().__init__(convert_charrefs=True)
		self.parts = []
		self._skipping = 0

	def handle_starttag(self, tag, attrs):
		if tag in self._SKIP:
			self._skipping += 1
		elif tag in self._BLOCK:
			self.parts.append("\n")

	def handle_endtag(self, tag):
		if tag in self._SKIP:
			self._skipping = max(0, self._skipping - 1)
		elif tag in self._BLOCK:
			self.parts.append("\n")

	def handle_data(self, data):
		if not self._skipping:
			self.parts.append(data)


def html_to_text(markup, limit=6000):
	"""Readable plain text from HTML: scripts and styles dropped, blocks become lines."""
	extractor = _TextExtractor()
	try:
		extractor.feed(markup)
		extractor.close()
	except Exception:
		pass
	lines = [" ".join(line.split()) for line in "".join(extractor.parts).splitlines()]
	text = "\n".join(line for line in lines if line)
	if len(text) > limit:
		text = text[:limit].rsplit(" ", 1)[0] + "..."
	return text


def _local(tag):
	return tag.rsplit("}", 1)[-1]


def _child_text(node, names):
	for child in node:
		if _local(child.tag) in names:
			text = (child.text or "").strip()
			if text:
				return text
			if child.get("href"):
				return child.get("href")
	return ""


def parse_feed(raw, limit=10):
	"""[(title, link, summary)] from an RSS or Atom document."""
	try:
		root = ET.fromstring(raw)
	except ET.ParseError:
		raise ResearchError("badresponse")
	entries = []
	for node in root.iter():
		if _local(node.tag) not in ("item", "entry"):
			continue
		title = html_to_text(_child_text(node, ("title",)), 300)
		if not title:
			continue
		link = _child_text(node, ("link",))
		summary = html_to_text(_child_text(node, ("description", "summary", "content")), 300)
		entries.append((title, link, summary))
		if len(entries) >= limit:
			break
	return entries


# ---------------------------------------------------------------- URLs

def is_web_url(url):
	return bool(re.match(r"^https?://[^\s]+$", url or "", re.I))


def fill_url(template, query, lang="en"):
	"""Substitute {query} (URL-encoded), {raw} and {lang} into a web address template."""
	return (template.replace("{query}", urllib.parse.quote(query, safe=""))
		.replace("{raw}", query).replace("{lang}", lang))
