# -*- coding: UTF-8 -*-
# Research It - the Research It dialog (like JAWS's), plus a manager for your own sources.

import json

import addonHandler
import wx
import gui
from gui import guiHelper
from logHandler import log

from . import actions, sources, store

addonHandler.initTranslation()


class _BaseDialog(wx.Dialog):
	_instance = None

	def __init__(self, parent, title, **kwargs):
		super().__init__(parent, title=title, **kwargs)
		type(self)._instance = self
		self.Bind(wx.EVT_CLOSE, lambda evt: self.close())

	def Destroy(self):
		if type(self)._instance is self:
			type(self)._instance = None
		return super().Destroy()

	def close(self):
		if self.IsModal():
			self.EndModal(wx.ID_CLOSE)
		else:
			self.Destroy()

	def _layout(self, helper):
		root = wx.BoxSizer(wx.VERTICAL)
		root.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		root.Fit(self)
		self.SetSizer(root)
		self.CentreOnScreen()


CURRENCIES = [
	("USD", _("US Dollar (USD)")),
	("INR", _("Indian Rupee (INR)")),
	("EUR", _("Euro (EUR)")),
	("GBP", _("British Pound (GBP)")),
	("JPY", _("Japanese Yen (JPY)")),
	("CAD", _("Canadian Dollar (CAD)")),
	("AUD", _("Australian Dollar (AUD)")),
	("SGD", _("Singapore Dollar (SGD)")),
	("CHF", _("Swiss Franc (CHF)")),
	("CNY", _("Chinese Yuan (CNY)")),
	("AED", _("UAE Dirham (AED)")),
	("NZD", _("New Zealand Dollar (NZD)")),
	("HKD", _("Hong Kong Dollar (HKD)")),
	("SAR", _("Saudi Riyal (SAR)")),
	("MYR", _("Malaysian Ringgit (MYR)")),
	("THB", _("Thai Baht (THB)")),
	("KRW", _("South Korean Won (KRW)")),
	("ZAR", _("South African Rand (ZAR)")),
	("BRL", _("Brazilian Real (BRL)")),
	("MXN", _("Mexican Peso (MXN)")),
]


class CurrencyDialog(wx.Dialog):
	"""Currency conversion form with labelled, keyboard-accessible dropdowns."""

	def __init__(self, parent):
		super().__init__(parent, title=_("Currency converter"))
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.amountEdit = helper.addLabeledControl(
			_("&Amount:"), wx.TextCtrl, value="1", style=wx.TE_PROCESS_ENTER
		)
		labels = [label for _code, label in CURRENCIES]
		self.fromChoice = helper.addLabeledControl(
			_("&From currency:"), wx.Choice, choices=labels
		)
		self.toChoice = helper.addLabeledControl(
			_("&To currency:"), wx.Choice, choices=labels
		)
		self.fromChoice.SetSelection(0)  # USD
		self.toChoice.SetSelection(1)    # INR
		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		convert = buttons.addButton(self, label=_("&Convert"))
		convert.SetDefault()
		convert.Bind(wx.EVT_BUTTON, self.onConvert)
		buttons.addButton(self, id=wx.ID_CANCEL, label=_("&Cancel")).Bind(
			wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CANCEL)
		)
		helper.addItem(buttons)
		root = wx.BoxSizer(wx.VERTICAL)
		root.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		root.Fit(self)
		self.SetSizer(root)
		self.SetEscapeId(wx.ID_CANCEL)
		self.CentreOnScreen()
		self.amountEdit.SetFocus()
		self.query = None
		self.amountEdit.Bind(wx.EVT_TEXT_ENTER, self.onConvert)

	def onConvert(self, evt):
		raw_amount = self.amountEdit.GetValue().strip().replace(",", "")
		try:
			amount = float(raw_amount)
			if amount <= 0:
				raise ValueError
		except ValueError:
			wx.MessageBox(
				_("Enter a valid amount greater than zero."),
				_("Currency converter"), wx.OK | wx.ICON_WARNING, self,
			)
			self.amountEdit.SetFocus()
			return
		from_code = CURRENCIES[self.fromChoice.GetSelection()][0]
		to_code = CURRENCIES[self.toChoice.GetSelection()][0]
		self.query = "%s %s to %s" % (raw_amount, from_code, to_code)
		self.EndModal(wx.ID_OK)


def show_currency_dialog():
	"""Show the currency form and run the selected conversion."""
	dialog = CurrencyDialog(gui.mainFrame)
	gui.mainFrame.prePopup()
	try:
		result = dialog.ShowModal()
		query = dialog.query
	finally:
		dialog.Destroy()
		gui.mainFrame.postPopup()
	if result == wx.ID_OK and query:
		actions.research(sources.BUILTIN_BY_ID["currency"], query)


class ResearchDialog(_BaseDialog):
	"""Type or confirm the text, pick a source, press Enter. Results open in the results window."""

	def __init__(self, parent, query=""):
		super().__init__(parent, _("Quick Research"))
		self.sources = actions.visible_sources()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.queryEdit = helper.addLabeledControl(
			_("&Text to research:"), wx.TextCtrl, value=query, style=wx.TE_PROCESS_ENTER
		)
		self.queryEdit.Bind(wx.EVT_TEXT_ENTER, self.onResearch)
		self.sourceList = helper.addLabeledControl(
			_("&Source:"), wx.ListBox, choices=[s.label(_) for s in self.sources], size=self.FromDIP(wx.Size(380, 200))
		)
		self.sourceList.Bind(wx.EVT_LISTBOX_DCLICK, self.onResearch)
		c = store.conf()
		preferred = c["lastSource"] or c["defaultSource"]
		ids = [s.id for s in self.sources]
		self.sourceList.SetSelection(ids.index(preferred) if preferred in ids else 0)
		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		research = buttons.addButton(self, label=_("&Research"))
		research.SetDefault()
		research.Bind(wx.EVT_BUTTON, self.onResearch)
		buttons.addButton(self, label=_("Manage &sources...")).Bind(wx.EVT_BUTTON, self.onManage)
		buttons.addButton(self, id=wx.ID_CLOSE, label=_("&Close")).Bind(wx.EVT_BUTTON, lambda evt: self.close())
		helper.addItem(buttons)
		self._layout(helper)
		self.SetEscapeId(wx.ID_CLOSE)
		# With text already selected the source list is what you want; otherwise you need to type.
		(self.sourceList if query else self.queryEdit).SetFocus()

	def onResearch(self, evt):
		index = self.sourceList.GetSelection()
		if index == wx.NOT_FOUND:
			return
		source, query = self.sources[index], self.queryEdit.GetValue()
		self.close()
		if source.id == "currency":
			wx.CallAfter(show_currency_dialog)
		else:
			wx.CallAfter(actions.research, source, query)

	def onManage(self, evt):
		dialog = SourcesDialog(self)
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()
		self.sources = actions.visible_sources()
		self.sourceList.Set([s.label(_) for s in self.sources])
		if self.sources:
			self.sourceList.SetSelection(0)


class ResultsDialog(_BaseDialog):
	"""Accessible results view with a direct route to research another term."""

	def __init__(self, parent, title, text):
		super().__init__(parent, title=title, size=wx.Size(720, 520))
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.resultsText = wx.TextCtrl(
			self, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
			size=self.FromDIP(wx.Size(680, 410)),
		)
		helper.addItem(self.resultsText)
		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		research = buttons.addButton(self, label=_("&Research another term"))
		research.Bind(wx.EVT_BUTTON, self.onResearchAnother)
		close = buttons.addButton(self, id=wx.ID_CLOSE, label=_("&Close"))
		close.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CLOSE))
		helper.addItem(buttons)
		self.SetEscapeId(wx.ID_CLOSE)
		self._layout(helper)
		self.resultsText.SetFocus()

	def onResearchAnother(self, evt):
		self.EndModal(wx.ID_OK)


def show_results(doc, title):
	"""Show results; return to the normal modeless search dialog on request."""
	dialog = ResultsDialog(gui.mainFrame, title, doc.to_text())
	gui.mainFrame.prePopup()
	try:
		result = dialog.ShowModal()
	finally:
		dialog.Destroy()
		gui.mainFrame.postPopup()

	# Reopen search using the exact same modeless path as the add-on's
	# NVDA+Alt+R command. Do not create a second nested modal dialog here:
	# NVDA's popup bookkeeping and wx modal state can otherwise dismiss it.
	if result == wx.ID_OK:
		def open_next_search():
			from . import _show_research_dialog
			_show_research_dialog("")
		wx.CallAfter(open_next_search)


def _type_label(kind):
	return {
		"browser": _("Open in browser"),
		"rss": _("News feed (RSS)"),
		"json": _("JSON data"),
		"text": _("Web page text"),
	}[kind]


class SourceEditDialog(wx.Dialog):
	"""Add or edit one custom source."""

	def __init__(self, parent, spec=None):
		super().__init__(parent, title=_("Edit source") if spec else _("Add source"))
		spec = spec or {"type": "browser", "needs_query": True}
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.nameEdit = helper.addLabeledControl(_("Source &name:"), wx.TextCtrl, value=spec.get("name", ""))
		self.typeChoice = helper.addLabeledControl(
			_("&Type:"), wx.Choice, choices=[_type_label(k) for k in sources.CUSTOM_TYPES]
		)
		self.typeChoice.SetSelection(sources.CUSTOM_TYPES.index(spec.get("type", "browser")))
		self.typeChoice.Bind(wx.EVT_CHOICE, lambda evt: self.updateFields())
		self.urlEdit = helper.addLabeledControl(
			_("&Web address, using {query} for the text:"), wx.TextCtrl, value=spec.get("url", "")
		)
		self.fieldsEdit = helper.addLabeledControl(
			_("JSON &fields, one per line as label=path:"), wx.TextCtrl,
			value=spec.get("fields", ""), style=wx.TE_MULTILINE, size=self.FromDIP(wx.Size(380, 90)),
		)
		self.needsCheck = helper.addItem(wx.CheckBox(self, label=_("This source needs &text to research")))
		self.needsCheck.SetValue(bool(spec.get("needs_query", True)))
		helper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK | wx.CANCEL))
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		root = wx.BoxSizer(wx.VERTICAL)
		root.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		root.Fit(self)
		self.SetSizer(root)
		self.CentreOnScreen()
		self.updateFields()
		self.nameEdit.SetFocus()

	def updateFields(self):
		self.fieldsEdit.Enable(sources.CUSTOM_TYPES[self.typeChoice.GetSelection()] == "json")

	def spec(self):
		return {
			"name": self.nameEdit.GetValue().strip(),
			"type": sources.CUSTOM_TYPES[self.typeChoice.GetSelection()],
			"url": self.urlEdit.GetValue().strip(),
			"fields": self.fieldsEdit.GetValue().strip(),
			"needs_query": self.needsCheck.GetValue(),
		}

	def onOk(self, evt):
		if sources.validate_spec(self.spec()) is not None:
			wx.MessageBox(
				_("Please enter a name and a web address starting with http or https"),
				_("Quick Research"), wx.OK | wx.ICON_ERROR, self,
			)
			return
		evt.Skip()


class SourcesDialog(_BaseDialog):
	"""Add, edit, remove, import and export your own sources."""

	def __init__(self, parent):
		super().__init__(parent, _("Quick Research sources"))
		self.specs = store.custom_specs()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.list = helper.addLabeledControl(
			_("Custom sources"), wx.ListBox, choices=[], size=self.FromDIP(wx.Size(420, 180))
		)
		self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.onEdit)
		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		for label, handler in (
			(_("&Add..."), self.onAdd), (_("&Edit..."), self.onEdit), (_("&Remove"), self.onRemove),
			(_("&Import..."), self.onImport), (_("E&xport..."), self.onExport),
		):
			buttons.addButton(self, label=label).Bind(wx.EVT_BUTTON, handler)
		buttons.addButton(self, id=wx.ID_CLOSE, label=_("&Close")).Bind(wx.EVT_BUTTON, lambda evt: self.close())
		helper.addItem(buttons)
		self._layout(helper)
		self.SetEscapeId(wx.ID_CLOSE)
		self.refresh()
		self.list.SetFocus()

	def refresh(self, select=0):
		self.list.Set(["%s (%s)" % (s.get("name", ""), _type_label(s.get("type", "browser"))) for s in self.specs])
		if self.specs:
			self.list.SetSelection(max(0, min(select, len(self.specs) - 1)))

	def _save(self):
		store.save_custom_specs(self.specs)

	def _edit(self, spec):
		dialog = SourceEditDialog(self, spec)
		try:
			return dialog.spec() if dialog.ShowModal() == wx.ID_OK else None
		finally:
			dialog.Destroy()

	def onAdd(self, evt):
		spec = self._edit(None)
		if spec:
			self.specs = [s for s in self.specs if s.get("name") != spec["name"]] + [spec]
			self._save()
			self.refresh(len(self.specs) - 1)

	def onEdit(self, evt):
		index = self.list.GetSelection()
		if index == wx.NOT_FOUND:
			return
		spec = self._edit(self.specs[index])
		if spec:
			self.specs[index] = spec
			self._save()
			self.refresh(index)

	def onRemove(self, evt):
		index = self.list.GetSelection()
		if index == wx.NOT_FOUND:
			return
		del self.specs[index]
		self._save()
		self.refresh(index)

	def onImport(self, evt):
		with wx.FileDialog(self, _("Import sources"), wildcard=_("JSON files (*.json)|*.json"),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as chooser:
			if chooser.ShowModal() != wx.ID_OK:
				return
			path = chooser.GetPath()
		try:
			with open(path, encoding="utf-8") as handle:
				incoming = json.load(handle)
			valid = [s for s in incoming if sources.validate_spec(s) is None]
		except (OSError, ValueError, TypeError):
			log.debugWarning("ResearchIt: import failed", exc_info=True)
			actions.report(ValueError("import"))
			return
		names = set(s["name"] for s in valid)
		self.specs = [s for s in self.specs if s.get("name") not in names] + valid
		self._save()
		self.refresh()
		actions.speak(_("Imported {count} sources").format(count=len(valid)))

	def onExport(self, evt):
		with wx.FileDialog(self, _("Export sources"), defaultFile="quickresearch-sources.json",
				wildcard=_("JSON files (*.json)|*.json"), style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as chooser:
			if chooser.ShowModal() != wx.ID_OK:
				return
			path = chooser.GetPath()
		try:
			with open(path, "w", encoding="utf-8") as handle:
				json.dump(self.specs, handle, ensure_ascii=False, indent=2)
		except OSError as error:
			actions.report(error)
			return
		actions.speak(_("Exported sources to {path}").format(path=path))
