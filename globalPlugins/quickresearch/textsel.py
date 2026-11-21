# -*- coding: UTF-8 -*-
# Research It - find the text to research: selection, then the word at the cursor, then the clipboard.

import api
import textInfos

_EDGE_PUNCTUATION = " \t\r\n.,;:!?\"'()[]{}<>"
MAX_LENGTH = 300


def _clean(text):
	return " ".join((text or "").split())[:MAX_LENGTH]


def get_query(use_word=True, use_clipboard=True):
	"""Return (text, where) with where one of 'selection', 'word', 'clipboard', or ('', None)."""
	obj = api.getFocusObject()
	interceptor = getattr(obj, "treeInterceptor", None)
	if interceptor is not None and hasattr(interceptor, "TextInfo") and not getattr(interceptor, "passThrough", False):
		obj = interceptor
	try:
		selection = obj.makeTextInfo(textInfos.POSITION_SELECTION)
		if not selection.isCollapsed and _clean(selection.text):
			return _clean(selection.text), "selection"
	except (RuntimeError, NotImplementedError, AttributeError):
		pass
	if use_word:
		try:
			caret = obj.makeTextInfo(textInfos.POSITION_CARET)
			caret.expand(textInfos.UNIT_WORD)
			word = caret.text.strip(_EDGE_PUNCTUATION)
			if word:
				return _clean(word), "word"
		except (RuntimeError, NotImplementedError, AttributeError):
			pass
	if use_clipboard:
		try:
			clip = api.getClipData()
		except Exception:
			clip = ""
		if clip and len(clip) <= MAX_LENGTH * 2 and _clean(clip):
			return _clean(clip), "clipboard"
	return "", None
