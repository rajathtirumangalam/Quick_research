# -*- coding: UTF-8 -*-
# Research It - the sources you can research with. Pure logic: the network function and the
# translator arrive through Context, so every source can be tested with canned responses.

import json
import urllib.parse
from collections import namedtuple

from . import parsing
from .parsing import Doc, ResearchError


def N_(text):
	"""Marks a string for translation without translating it yet."""
	return text


# tr: translator for result text; fetch(url, timeout) -> bytes
Context = namedtuple(
	"Context", "tr fetch timeout news_count home_currency default_city fahrenheit wiki_lang"
)
# Either a document to show, or a web address to open in the browser.
Result = namedtuple("Result", "doc open_url")

WIKTIONARY_API = "https://en.wiktionary.org/w/api.php"
WIKIPEDIA_API = "https://%s.wikipedia.org/w/api.php"
GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"
CURRENCY_API = "https://api.frankfurter.dev/v1/latest"


class Source:
	def __init__(self, source_id, name, needs_query, run, custom=False, translate=True):
		self.id = source_id
		self.name = name
		self.needs_query = needs_query
		self.run = run  # run(query, ctx) -> Result
		self.custom = custom
		self.translate = translate

	def label(self, translator):
		return translator(self.name) if self.translate else self.name


def _json(ctx, url):
	raw = ctx.fetch(url, ctx.timeout)
	try:
		return json.loads(raw.decode("utf-8"))
	except (ValueError, UnicodeDecodeError):
		raise ResearchError("badresponse")


def _language(query, ctx):
	return ctx.wiki_lang if ctx.wiki_lang in parsing.WIKI_LANGUAGES else parsing.detect_language(query)


def _need_text(query):
	text = " ".join((query or "").split())
	if not text:
		raise ResearchError("empty")
	return text


# ---------------------------------------------------------------- dictionary

def _wiktionary_page(ctx, word):
	params = {
		"action": "query", "prop": "extracts", "explaintext": 1, "exsectionformat": "wiki",
		"redirects": 1, "format": "json", "titles": word,
	}
	pages = (_json(ctx, WIKTIONARY_API + "?" + urllib.parse.urlencode(params)).get("query") or {}).get("pages") or {}
	page = next(iter(pages.values()), None)
	if not page or "missing" in page or not page.get("extract"):
		return None
	return page


def run_dictionary(query, ctx):
	word = _need_text(query)
	page = _wiktionary_page(ctx, word)
	if page is None and word != word.lower():
		page = _wiktionary_page(ctx, word.lower())
	if page is None:
		raise ResearchError("nothing", query=word)
	names = parsing.WIKTIONARY_SECTIONS.get(_language(word, ctx), ["English"])
	sections = parsing.parse_wiktionary(page["extract"], names)
	doc = Doc(page.get("title", word))
	doc.heading(page.get("title", word))
	if sections:
		for title, lines in sections:
			doc.heading(title, 3)
			if len(lines) > 1 and title.split(" ")[0] not in ("Etymology", "Pronunciation"):
				doc.para(lines[0])
				doc.items(lines[1:])
			else:
				for line in lines:
					doc.para(line)
	else:
		# The page exists but its layout was not recognised: show the beginning of it.
		for line in [l for l in page["extract"].splitlines() if l.strip() and not l.startswith("=")][:25]:
			doc.para(line.strip())
	doc.para(ctx.tr("Source: {url}").format(
		url="https://en.wiktionary.org/wiki/" + urllib.parse.quote(page.get("title", word).replace(" ", "_"))))
	return Result(doc, None)


# ---------------------------------------------------------------- Wikipedia

def run_wikipedia(query, ctx):
	text = _need_text(query)
	lang = _language(text, ctx)
	pages = []
	for code in ([lang] + (["en"] if lang != "en" else [])):
		params = {
			"action": "query", "generator": "search", "gsrsearch": text, "gsrlimit": 5,
			"prop": "extracts|info", "exintro": 1, "explaintext": 1, "exlimit": "max",
			"inprop": "url", "redirects": 1, "format": "json",
		}
		found = list(((_json(ctx, (WIKIPEDIA_API % code) + "?" + urllib.parse.urlencode(params))
			.get("query") or {}).get("pages") or {}).values())
		found.sort(key=lambda page: page.get("index", 99))
		if found:
			pages = found
			break
	if not pages:
		raise ResearchError("nothing", query=text)
	main = next((page for page in pages if page.get("extract")), pages[0])
	doc = Doc(main.get("title", text))
	doc.heading(main.get("title", text))
	for paragraph in [p for p in (main.get("extract") or "").split("\n") if p.strip()]:
		doc.para(paragraph.strip())
	others = [page["title"] for page in pages if page is not main and page.get("title")]
	if others:
		doc.heading(ctx.tr("Other matches"), 3)
		doc.items(others)
	if main.get("fullurl"):
		doc.para(ctx.tr("Source: {url}").format(url=main["fullurl"]), link=main["fullurl"])
	return Result(doc, None)


# ---------------------------------------------------------------- weather and time (Open-Meteo)

def _geocode(place, ctx):
	params = {"name": place, "count": 1, "language": parsing.detect_language(place), "format": "json"}
	results = _json(ctx, GEOCODING_API + "?" + urllib.parse.urlencode(params)).get("results") or []
	if not results:
		raise ResearchError("nothing", query=place)
	first = results[0]
	label = ", ".join(part for part in (first.get("name"), first.get("admin1"), first.get("country")) if part)
	return first["latitude"], first["longitude"], label


def _city(query, ctx):
	place = " ".join((query or "").split()) or ctx.default_city
	if not place:
		raise ResearchError("needcity")
	return place


def wmo_text(code, tr):
	"""Plain-language condition for a WMO weather code."""
	if code == 0:
		return tr("Clear sky")
	if code in (1, 2, 3):
		return tr("Cloudy")
	if code in (45, 48):
		return tr("Fog")
	if 51 <= code <= 67 or 80 <= code <= 82:
		return tr("Rain")
	if 71 <= code <= 77 or 85 <= code <= 86:
		return tr("Snow")
	if 95 <= code <= 99:
		return tr("Thunderstorm")
	return ""


def run_weather(query, ctx):
	lat, lon, label = _geocode(_city(query, ctx), ctx)
	params = {
		"latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 3,
		"current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
		"daily": "weather_code,temperature_2m_max,temperature_2m_min",
		"temperature_unit": "fahrenheit" if ctx.fahrenheit else "celsius",
	}
	data = _json(ctx, FORECAST_API + "?" + urllib.parse.urlencode(params))
	current, daily = data.get("current"), data.get("daily")
	if not current or not daily:
		raise ResearchError("badresponse")
	unit = "F" if ctx.fahrenheit else "C"

	def degrees(value):
		return "%d\u00b0%s" % (round(value), unit)

	title = ctx.tr("Weather in {place}").format(place=label)
	doc = Doc(title)
	doc.heading(title)
	doc.heading(ctx.tr("Now"), 3)
	doc.para(ctx.tr(
		"{condition}, {temperature}. Feels like {feels}. Humidity {humidity} percent. Wind {wind} kilometres per hour."
	).format(
		condition=wmo_text(current.get("weather_code", -1), ctx.tr),
		temperature=degrees(current["temperature_2m"]), feels=degrees(current["apparent_temperature"]),
		humidity=round(current["relative_humidity_2m"]), wind=round(current["wind_speed_10m"]),
	))
	doc.heading(ctx.tr("Forecast"), 3)
	lines = []
	for day, code, high, low in zip(daily["time"], daily["weather_code"],
			daily["temperature_2m_max"], daily["temperature_2m_min"]):
		lines.append(ctx.tr("{day}: {condition}, high {high}, low {low}.").format(
			day=day, condition=wmo_text(code, ctx.tr), high=degrees(high), low=degrees(low)))
	doc.items(lines)
	return Result(doc, None)


def run_time(query, ctx):
	lat, lon, label = _geocode(_city(query, ctx), ctx)
	params = {"latitude": lat, "longitude": lon, "timezone": "auto", "current": "temperature_2m"}
	data = _json(ctx, FORECAST_API + "?" + urllib.parse.urlencode(params))
	stamp = (data.get("current") or {}).get("time")
	if not stamp or "T" not in stamp:
		raise ResearchError("badresponse")
	date, clock = stamp.split("T", 1)
	title = ctx.tr("Time in {place}").format(place=label)
	doc = Doc(title)
	doc.heading(title)
	doc.para(ctx.tr("It is {time} on {date} in {place}, time zone {zone}.").format(
		time=clock, date=date, place=label, zone=data.get("timezone", "")))
	return Result(doc, None)


# ---------------------------------------------------------------- currency (ECB reference rates)

def run_currency(query, ctx):
	# Use INR as the fallback home currency when none has been configured.
	parsed = parsing.parse_currency(query or "", ctx.home_currency or "INR")
	if parsed is None:
		raise ResearchError("needamount")
	amount, source, target = parsed
	if source == target:
		rate, date = 1.0, ""
	else:
		params = {"base": source, "symbols": target}
		try:
			data = _json(ctx, CURRENCY_API + "?" + urllib.parse.urlencode(params))
		except ResearchError as error:
			if error.kind == "nothing":
				raise ResearchError("nothing", query=query)
			raise
		rate = (data.get("rates") or {}).get(target)
		if rate is None:
			raise ResearchError("nothing", query=query)
		date = data.get("date", "")
	headline = "%s %s = %s %s" % (parsing.format_amount(amount), source, parsing.format_amount(amount * rate), target)
	doc = Doc(headline)
	doc.heading(headline)
	if date:
		doc.para(ctx.tr("Exchange rates from the European Central Bank, {date}").format(date=date))
	return Result(doc, None)


# ---------------------------------------------------------------- news feeds and browser sources

def feed_runner(name, url):
	def run(query, ctx):
		entries = parsing.parse_feed(ctx.fetch(url, ctx.timeout), ctx.news_count)
		if not entries:
			raise ResearchError("nothing", query=name)
		doc = Doc(name)
		for title, link, summary in entries:
			doc.heading(title, 2)
			if summary and summary != title:
				doc.para(summary, link=link or None)
		return Result(doc, None)
	return run


def browser_runner(template):
	def run(query, ctx):
		text = _need_text(query)
		return Result(None, parsing.fill_url(template, text, _language(text, ctx)))
	return run


BUILTINS = [
	Source("dictionary", N_("Dictionary (Wiktionary)"), True, run_dictionary),
	Source("wikipedia", N_("Wikipedia"), True, run_wikipedia),
	Source("weather", N_("Weather"), False, run_weather),
	Source("time", N_("Time in a city"), False, run_time),
	Source("currency", N_("Currency converter"), True, run_currency),
	Source("news_bbc", "BBC News", False, feed_runner("BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
		translate=False),
	Source("news_hindu", "The Hindu", False,
		feed_runner("The Hindu", "https://www.thehindu.com/news/national/feeder/default.rss"), translate=False),
	Source("news_ndtv", "NDTV", False,
		feed_runner("NDTV", "https://feeds.feedburner.com/ndtvnews-top-stories"), translate=False),
	Source("news_toi", "Times of India", False,
		feed_runner("Times of India", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"), translate=False),
	Source("web", N_("Web search (opens your browser)"), True,
		browser_runner("https://duckduckgo.com/?q={query}")),
	Source("maps", N_("Maps (opens your browser)"), True,
		browser_runner("https://www.google.com/maps/search/{query}")),
]
BUILTIN_BY_ID = {source.id: source for source in BUILTINS}
NEWS_SOURCE_IDS = [source.id for source in BUILTINS if source.id.startswith("news_")]


# ---------------------------------------------------------------- user-defined sources

CUSTOM_TYPES = ["browser", "rss", "json", "text"]


def validate_spec(spec):
	"""None if the custom source definition is usable, else a short reason code."""
	if not isinstance(spec, dict):
		return "invalid"
	if not str(spec.get("name", "")).strip():
		return "name"
	if spec.get("type") not in CUSTOM_TYPES:
		return "type"
	if not parsing.is_web_url(str(spec.get("url", "")).replace("{query}", "x").replace("{raw}", "x").replace("{lang}", "en")):
		return "url"
	return None


def _field_pairs(text):
	pairs = []
	for line in (text or "").splitlines():
		line = line.strip()
		if not line:
			continue
		label, sep, path = line.partition("=")
		pairs.append((label.strip(), path.strip()) if sep else (line, line))
	return pairs


def custom_source(spec):
	kind, template = spec["type"], spec["url"]
	name = spec["name"].strip()

	def run(query, ctx):
		text = " ".join((query or "").split())
		if kind == "browser":
			return Result(None, parsing.fill_url(template, text, _language(text, ctx)))
		url = parsing.fill_url(template, text, _language(text, ctx))
		raw = ctx.fetch(url, ctx.timeout)
		doc = Doc(name)
		doc.heading(name)
		if kind == "rss":
			for title, link, summary in parsing.parse_feed(raw, ctx.news_count):
				doc.heading(title, 3)
				if summary and summary != title:
					doc.para(summary, link=link or None)
		elif kind == "json":
			try:
				data = json.loads(raw.decode("utf-8"))
			except (ValueError, UnicodeDecodeError):
				raise ResearchError("badresponse")
			for label, path in _field_pairs(spec.get("fields", "")):
				values = parsing.json_values(data, path)
				if values:
					doc.heading(label, 3)
					doc.items(values)
		else:
			body = parsing.html_to_text(raw.decode("utf-8", "replace"))
			for paragraph in body.split("\n"):
				doc.para(paragraph)
		if not doc.blocks[1:]:
			raise ResearchError("nothing", query=text or name)
		return Result(doc, None)

	return Source("custom:" + name, name, bool(spec.get("needs_query", True)), run, custom=True, translate=False)


def available_sources(custom_specs, hidden_ids=()):
	"""Sources for the dialog: visible built-ins first, then valid custom ones."""
	shown = [source for source in BUILTINS if source.id not in set(hidden_ids)]
	return shown + [custom_source(spec) for spec in custom_specs if validate_spec(spec) is None]
