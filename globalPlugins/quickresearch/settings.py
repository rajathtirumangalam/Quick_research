# -*- coding: UTF-8 -*-
# Research It - NVDA settings panel.

import addonHandler
import wx
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsPanel

from . import actions, feedback, sources, store

addonHandler.initTranslation()


class ResearchItPanel(SettingsPanel):
	title = _("Quick Research")

	def makeSettings(self, settingsSizer):
		c = store.conf()
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		self._msgCodes = [""] + [code for code, _name in feedback.LANGUAGES]
		self.msgLang = helper.addLabeledControl(
			_("&Language of spoken messages:"), wx.Choice,
			choices=[_("Follow NVDA language")] + [name for _code, name in feedback.LANGUAGES],
		)
		self.msgLang.SetSelection(self._msgCodes.index(c["messageLanguage"]) if c["messageLanguage"] in self._msgCodes else 0)

		self.presentation = helper.addLabeledControl(
			_("Show &results in:"), wx.Choice, choices=[_("Results window"), _("Speech"), _("Window and speech")]
		)
		self.presentation.SetSelection(c["presentation"])

		self._sources = actions.visible_sources() + [
			s for s in sources.BUILTINS if s.id in set(c["hiddenSources"])
		]
		self.defaultSource = helper.addLabeledControl(
			_("&Default source for quick lookup:"), wx.Choice, choices=[s.label(_) for s in self._sources]
		)
		ids = [s.id for s in self._sources]
		self.defaultSource.SetSelection(ids.index(c["defaultSource"]) if c["defaultSource"] in ids else 0)

		self._wikiCodes = ["auto"] + [code for code, _name in feedback.LANGUAGES]
		self.wikiLang = helper.addLabeledControl(
			_("&Wikipedia and dictionary language:"), wx.Choice,
			choices=[_("Detect from the text")] + [name for _code, name in feedback.LANGUAGES],
		)
		self.wikiLang.SetSelection(self._wikiCodes.index(c["wikiLanguage"]) if c["wikiLanguage"] in self._wikiCodes else 0)

		self.city = helper.addLabeledControl(_("&Default city for weather and time:"), wx.TextCtrl, value=c["defaultCity"])
		self.currency = helper.addLabeledControl(
			_("&Home currency (three letters, for example INR):"), wx.TextCtrl, value=c["homeCurrency"]
		)
		self.unit = helper.addLabeledControl(
			_("Temperature &unit:"), wx.Choice, choices=[_("Celsius"), _("Fahrenheit")]
		)
		self.unit.SetSelection(c["temperatureUnit"])
		self.news = helper.addLabeledControl(
			_("&Number of news headlines:"), nvdaControls.SelectOnFocusSpinCtrl, min=1, max=30, initial=c["newsCount"]
		)
		self.timeout = helper.addLabeledControl(
			_("Network &timeout in seconds:"), nvdaControls.SelectOnFocusSpinCtrl, min=3, max=60, initial=c["timeout"]
		)
		self.word = helper.addItem(wx.CheckBox(self, label=_("Use the &word at the cursor when nothing is selected")))
		self.word.SetValue(c["useWord"])
		self.clip = helper.addItem(wx.CheckBox(self, label=_("Fall back to the &clipboard when nothing is selected")))
		self.clip.SetValue(c["useClipboard"])

		hidden = set(c["hiddenSources"])
		self.builtin = helper.addLabeledControl(
			_("&Built-in sources to show:"), wx.CheckListBox, choices=[s.label(_) for s in sources.BUILTINS]
		)
		self.builtin.SetCheckedItems([i for i, s in enumerate(sources.BUILTINS) if s.id not in hidden])
		manage = helper.addItem(wx.Button(self, label=_("Manage s&ources...")))
		manage.Bind(wx.EVT_BUTTON, self.onManage)

	def onManage(self, evt):
		from .dialogs import SourcesDialog
		dialog = SourcesDialog(self)
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()

	def onSave(self):
		c = store.conf()
		c["messageLanguage"] = self._msgCodes[self.msgLang.GetSelection()]
		c["presentation"] = self.presentation.GetSelection()
		c["defaultSource"] = self._sources[self.defaultSource.GetSelection()].id
		c["wikiLanguage"] = self._wikiCodes[self.wikiLang.GetSelection()]
		c["defaultCity"] = self.city.GetValue().strip()
		c["homeCurrency"] = self.currency.GetValue().strip().upper()[:3]
		c["temperatureUnit"] = self.unit.GetSelection()
		c["newsCount"] = self.news.GetValue()
		c["timeout"] = self.timeout.GetValue()
		c["useWord"] = self.word.GetValue()
		c["useClipboard"] = self.clip.GetValue()
		shown = set(self.builtin.GetCheckedItems())
		c["hiddenSources"] = [s.id for i, s in enumerate(sources.BUILTINS) if i not in shown]
