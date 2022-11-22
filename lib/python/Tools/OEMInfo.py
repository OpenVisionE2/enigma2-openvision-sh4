# -*- coding: utf-8 -*-
from Components.SystemInfo import BoxInfo
from Tools.Directories import fileReadLine

MODULE_NAME = __name__.split(".")[-1]

model = BoxInfo.getItem("model")
brand = BoxInfo.getItem("brand")
platform = BoxInfo.getItem("platform")
displaymodel = BoxInfo.getItem("displaymodel")
displaybrand = BoxInfo.getItem("displaybrand")

resellerBrand = fileReadLine("/proc/stb/info/brand", source=MODULE_NAME)
if resellerBrand:
	displaybrand = resellerBrand

resellerModel = fileReadLine("/proc/stb/info/model_name", source=MODULE_NAME)
if resellerModel:
	displaymodel = resellerModel


def getOEMShowModel():
	return model


def getOEMShowBrand():
	return brand


def getOEMShowDisplayModel():
	return displaymodel


def getOEMShowDisplayBrand():
	return displaybrand


def getOEMShowPlatform():
	return platform
