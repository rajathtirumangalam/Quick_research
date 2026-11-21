# -*- coding: UTF-8 -*-
# Research It - runs a lookup on a background thread so NVDA never waits for the network.

import threading

import wx
from logHandler import log

from .parsing import ResearchError


class Engine:
	def __init__(self):
		self._generation = 0

	def cancel(self):
		"""Ignore the result of any lookup still in progress."""
		self._generation += 1

	def start(self, source, query, ctx, on_result, on_error):
		self._generation += 1
		generation = self._generation

		def finish(outcome):
			if generation != self._generation:
				return  # superseded by a newer lookup
			kind, payload = outcome
			(on_result if kind == "ok" else on_error)(payload)

		def work():
			try:
				outcome = ("ok", source.run(query, ctx))
			except ResearchError as error:
				outcome = ("fail", error)
			except Exception as error:
				log.error("ResearchIt: lookup failed", exc_info=True)
				outcome = ("fail", error)
			wx.CallAfter(finish, outcome)

		threading.Thread(target=work, name="ResearchItLookup", daemon=True).start()
