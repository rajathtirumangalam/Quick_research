# -*- coding: UTF-8 -*-
# Research It - configuration and custom source storage.

import json

import config

SECTION = "researchIt"

CONFSPEC = {
	"messageLanguage": "string(default='')",
	"presentation": "integer(default=0,min=0,max=2)",  # 0 results window, 1 speech, 2 both
	"defaultSource": "string(default='dictionary')",
	"lastSource": "string(default='')",
	"wikiLanguage": "string(default='auto')",
	"defaultCity": "string(default='')",
	"homeCurrency": "string(default='')",
	"temperatureUnit": "integer(default=0,min=0,max=1)",  # 0 Celsius, 1 Fahrenheit
	"newsCount": "integer(default=10,min=1,max=30)",
	"timeout": "integer(default=10,min=3,max=60)",
	"useWord": "boolean(default=True)",
	"useClipboard": "boolean(default=True)",
	"hiddenSources": "string_list(default=list())",
	"customSources": "string(default='[]')",
}


def register():
	config.conf.spec[SECTION] = CONFSPEC


def conf():
	return config.conf[SECTION]


def custom_specs():
	try:
		data = json.loads(conf()["customSources"] or "[]")
	except ValueError:
		return []
	return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def save_custom_specs(specs):
	conf()["customSources"] = json.dumps(specs, ensure_ascii=False)
