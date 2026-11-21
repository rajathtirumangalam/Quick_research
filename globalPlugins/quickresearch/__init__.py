# -*- coding: UTF-8 -*-
# Research It - look up the selected text (dictionary, Wikipedia, weather, time, currency, news, web).
# An NVDA take on the JAWS "Research It" feature.

import functools

import addonHandler
import globalPluginHandler
import globalVars
import gui
import scriptHandler
import wx
from gui.settingsDialogs import NVDASettingsDialog

from . import actions, dialogs, settings, store

addonHandler.initTranslation()

SCRCAT = _("Quick Research")


def disableInSecureMode(cls):
	"""Add-ons must not run on the secure desktop (sign-in and UAC screens)."""
	if getattr(globalVars.appArgs, "secure", False):
		return globalPluginHandler.GlobalPlugin
	return cls


def _guard(func):
	@functools.wraps(func)
	def wrapper(self, gesture):
		try:
			func(self, gesture)
		except Exception as error:
			actions.report(error)
	return wrapper


def _later(func, *args):
	def runner():
		try:
			func(*args)
		except Exception as error:
			actions.report(error)
	wx.CallAfter(runner)


def _show_research_dialog(query):
	instance = dialogs.ResearchDialog._instance
	if instance:
		try:
			instance.Raise()
			return
		except RuntimeError:
			pass  # the wx object is already gone
	gui.mainFrame.prePopup()
	try:
		dialogs.ResearchDialog(gui.mainFrame, query).Show()
	finally:
		gui.mainFrame.postPopup()


def _show_sources_dialog():
	gui.mainFrame.prePopup()
	try:
		dialog = dialogs.SourcesDialog(gui.mainFrame)
		dialog.ShowModal()
		dialog.Destroy()
	finally:
		gui.mainFrame.postPopup()


@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = SCRCAT

	def __init__(self):
		super().__init__()
		store.register()
		NVDASettingsDialog.categoryClasses.append(settings.ResearchItPanel)

	def terminate(self):
		try:
			NVDASettingsDialog.categoryClasses.remove(settings.ResearchItPanel)
		except ValueError:
			pass
		super().terminate()

	@scriptHandler.script(
		description=_("Opens the Quick Research dialog for the selected text"), gesture="kb:NVDA+alt+r"
	)
	@_guard
	def script_researchDialog(self, gesture):
		# Read the selection now, while it still exists; the dialog opens just after this script ends.
		_later(_show_research_dialog, actions.get_query())

	@scriptHandler.script(
		description=_("Researches the selected text with your default source"), gesture="kb:NVDA+alt+shift+r"
	)
	@_guard
	def script_quickLookup(self, gesture):
		actions.quick_lookup()

	@scriptHandler.script(description=_("Looks up the selected text in the dictionary"))
	@_guard
	def script_dictionary(self, gesture):
		actions.research_with("dictionary")

	@scriptHandler.script(description=_("Looks up the selected text on Wikipedia"))
	@_guard
	def script_wikipedia(self, gesture):
		actions.research_with("wikipedia")

	@scriptHandler.script(description=_("Speaks the weather for the selected city"))
	@_guard
	def script_weather(self, gesture):
		actions.research_with("weather", allow_word=False, allow_clipboard=False)

	@scriptHandler.script(description=_("Speaks the time in the selected city"))
	@_guard
	def script_time(self, gesture):
		actions.research_with("time", allow_word=False, allow_clipboard=False)

	@scriptHandler.script(description=_("Converts the selected currency amount"))
	@_guard
	def script_currency(self, gesture):
		actions.research_with("currency", allow_word=False)

	@scriptHandler.script(description=_("Reads the latest news headlines"))
	@_guard
	def script_news(self, gesture):
		actions.research_with("news_bbc", allow_word=False, allow_clipboard=False)

	@scriptHandler.script(description=_("Searches the web for the selected text"))
	@_guard
	def script_webSearch(self, gesture):
		actions.research_with("web")

	@scriptHandler.script(
		description=_("Shows the last research results again"), gesture="kb:NVDA+alt+control+r"
	)
	@_guard
	def script_showLast(self, gesture):
		actions.show_last()

	@scriptHandler.script(description=_("Copies the last research results to the clipboard"))
	@_guard
	def script_copyLast(self, gesture):
		actions.copy_last()

	@scriptHandler.script(description=_("Opens the Quick Research sources manager"))
	@_guard
	def script_sourcesManager(self, gesture):
		wx.CallAfter(_show_sources_dialog)

	@scriptHandler.script(description=_("Opens the Quick Research settings"))
	@_guard
	def script_openSettings(self, gesture):
		wx.CallAfter(gui.mainFrame.popupSettingsDialog, NVDASettingsDialog, settings.ResearchItPanel)
