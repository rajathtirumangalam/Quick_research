# -*- coding: UTF-8 -*-
# Research It - actions used by gesture scripts and dialogs.

import webbrowser

import addonHandler
import api
from logHandler import log

from . import feedback, netutil, sources, store, textsel
from .engine import Engine
from .feedback import L, speak

addonHandler.initTranslation()

_engine = Engine()
_last = {"doc": None, "title": ""}


def build_context():
	"""Snapshot of the settings on the main thread, for the background lookup."""
	c = store.conf()
	return sources.Context(
		tr=feedback.translator(), fetch=netutil.fetch, timeout=c["timeout"], news_count=c["newsCount"],
		home_currency=c["homeCurrency"].strip().upper(), default_city=c["defaultCity"].strip(),
		fahrenheit=c["temperatureUnit"] == 1, wiki_lang=c["wikiLanguage"],
	)


def visible_sources():
	return sources.available_sources(store.custom_specs(), set(store.conf()["hiddenSources"]))


def find_source(source_id):
	"""A source by id, including built-ins the user has hidden from the dialog."""
	if source_id in sources.BUILTIN_BY_ID:
		return sources.BUILTIN_BY_ID[source_id]
	return next((s for s in visible_sources() if s.id == source_id), sources.BUILTIN_BY_ID["dictionary"])


def source_label(source):
	return source.label(L)


def get_query(allow_word=True, allow_clipboard=True):
	c = store.conf()
	return textsel.get_query(allow_word and c["useWord"], allow_clipboard and c["useClipboard"])[0]


def report(error):
	"""Speak a friendly message for an error. Call from inside an except block."""
	if not hasattr(error, "kind"):
		log.error("ResearchIt error", exc_info=True)
	speak(feedback.error_message(error))


def research(source, query):
	query = " ".join((query or "").split())
	if source.needs_query and not query:
		speak(L("No text to research"))
		return
	store.conf()["lastSource"] = source.id
	speak(L("Searching {source}...").format(source=source_label(source)))

	def on_result(result):
		if result.open_url:
			try:
				webbrowser.open(result.open_url)
			except Exception as error:
				report(error)
				return
			speak(L("Opened {source} in your browser").format(source=source_label(source)))
			return
		_last["doc"], _last["title"] = result.doc, result.doc.title
		feedback.present(result.doc, result.doc.title, store.conf()["presentation"])

	def on_error(error):
		if getattr(error, "kind", "") == "nothing":
			error.info.setdefault("query", query)
		# Show the same accessible results window for empty matches and incomplete
		# currency input, so the user can immediately start another search.
		kind = getattr(error, "kind", "")
		if kind in ("nothing", "needamount"):
			from .parsing import Doc
			message = feedback.error_message(error)
			doc = Doc(message).heading(message)
			feedback.present(doc, message, 0)
		else:
			report(error)

	_engine.start(source, query, build_context(), on_result, on_error)


def quick_lookup():
	"""Research the selected text with the default source."""
	query = get_query()
	source = find_source(store.conf()["defaultSource"])
	research(source, query)


def research_with(source_id, allow_word=True, allow_clipboard=True):
	"""Research the current text with one specific built-in source."""
	research(find_source(source_id), get_query(allow_word, allow_clipboard))


def show_last():
	if _last["doc"] is None:
		speak(L("No results to show yet"))
		return
	feedback.present(_last["doc"], _last["title"], 0)


def copy_last():
	if _last["doc"] is None:
		speak(L("No results to show yet"))
		return
	api.copyToClip(_last["doc"].to_text())
	speak(L("Results copied to the clipboard"))
