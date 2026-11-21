# -*- coding: UTF-8 -*-
# Research It - speech, results window and the message-language override.

import gettext
import os

import addonHandler
import braille
import speech
import ui
import wx
from logHandler import log
from speech.commands import LangChangeCommand

from . import store

addonHandler.initTranslation()

# (language code, name written in that language)
LANGUAGES = [
	("en", "English"), ("hi", "हिन्दी"), ("bn", "বাংলা"), ("ta", "தமிழ்"), ("te", "తెలుగు"),
	("mr", "मराठी"), ("gu", "ગુજરાતી"), ("kn", "ಕನ್ನಡ"), ("ml", "മലയാളം"), ("pa", "ਪੰਜਾਬੀ"),
]

_ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
_LOCALE_DIR = os.path.join(_ADDON_ROOT, "locale")
_cache = {}


def _translation(lang):
	if lang not in _cache:
		try:
			_cache[lang] = gettext.translation("nvda", _LOCALE_DIR, languages=[lang], fallback=True)
		except Exception:
			log.debugWarning("ResearchIt: cannot load language %s" % lang, exc_info=True)
			_cache[lang] = gettext.NullTranslations()
	return _cache[lang]


def translator():
	"""A translate function for the chosen message language. Safe to hand to a background thread."""
	lang = store.conf()["messageLanguage"]
	return _translation(lang).gettext if lang else _


def L(msgid):
	return translator()(msgid)


def speak(text, interrupt=True):
	lang = store.conf()["messageLanguage"]
	if interrupt:
		try:
			speech.cancelSpeech()
		except Exception:
			pass
	if lang:
		try:
			speech.speak([LangChangeCommand(lang), text, LangChangeCommand(None)])
			braille.handler.message(text)
			return
		except Exception:
			log.debugWarning("ResearchIt: language-tagged speech failed", exc_info=True)
	ui.message(text)


def error_message(error):
	"""The spoken message for a ResearchError."""
	info = getattr(error, "info", {}) or {}
	kind = getattr(error, "kind", "")
	if kind == "empty":
		return L("No text to research")
	if kind == "nothing":
		return L("Nothing found for {query}").format(query=info.get("query", ""))
	if kind == "network":
		return L("Could not reach the service. Check your internet connection.")
	if kind == "badresponse":
		return L("The service returned an unexpected response")
	if kind == "needcity":
		return L("Type a city name, or set a default city in the Quick Research settings")
	if kind == "needamount":
		return L("Type an amount and currency, for example 100 USD to INR")
	return L("Unable to complete the action: {error}").format(error=error)


def present(doc, title, mode):
	"""Show results: 0 in the results window, 1 spoken, 2 both."""
	if mode in (1, 2):
		speak(doc.summary(700) or title)
	if mode in (0, 2):
		def show():
			from . import dialogs
			dialogs.show_results(doc, title)
		if mode == 2:
			wx.CallLater(600, show)
		else:
			show()
