# -*- coding: utf-8 -*-
from Components.config import config, ConfigSelection, ConfigSubDict, ConfigYesNo
from Components.SystemInfo import BoxInfo
from Tools.CList import CList
from os.path import isfile

has_scart = BoxInfo.getItem("scart")
has_yuv = BoxInfo.getItem("yuv")
has_rca = BoxInfo.getItem("rca")
has_avjack = BoxInfo.getItem("avjack")
Has24hz = BoxInfo.getItem("Has24hz")

# The "VideoHardware" is the interface to /proc/stb/video.
# It generates hotplug events, and gives you the list of
# available and preferred modes, as well as handling the currently
# selected mode. No other strict checking is done.

config.av.edid_override = ConfigYesNo(default=False)


class VideoHardware:
	rates = {} # high-level, use selectable modes.
	modes = {}  # a list of (high-level) modes for a certain port.

	rates["PAL"] = {"50Hz": {50: "pal"}}
	rates["NTSC"] = {"60Hz": {60: "ntsc"}}
	rates["480i"] = {"60Hz": {60: "480i"}}
	rates["576i"] = {"50Hz": {50: "576i"}}
	rates["480p"] = {"60Hz": {60: "480p"}}
	rates["576p"] = {"50Hz": {50: "576p"}}
	rates["720p"] = {"50Hz": {50: "720p50"}, "60Hz": {60: "720p"}, "multi": {50: "720p50", 60: "720p"}, "auto": {50: "720p50", 60: "720p"}}
	rates["1080i"] = {"50Hz": {50: "1080i50"}, "60Hz": {60: "1080i"}, "multi": {50: "1080i50", 60: "1080i"}, "auto": {50: "1080i50", 60: "1080i", 24: "1080i24"}}
	rates["1080p"] = {"23Hz": {23: "1080p23"}, "24Hz": {24: "1080p24"}, "25Hz": {25: "1080p25"}, "29Hz": {29: "1080p29"}, "30Hz": {30: "1080p30"}, "50Hz": {50: "1080p50"}, "59Hz": {59: "1080p59"}, "60Hz": {60: "1080p"}, "multi": {50: "1080p50", 60: "1080p"}, "auto": {50: "1080p50", 60: "1080p", 24: "1080p24"}}

	rates["PC"] = {
		"1024x768": {60: "1024x768", 70: "1024x768_70", 75: "1024x768_75", 90: "1024x768_90", 100: "1024x768_100"},
		"1280x1024": {60: "1280x1024", 70: "1280x1024_70", 75: "1280x1024_75"},
		"1600x1200": {60: "1600x1200_60"}
	}

	if has_scart:
		modes["Scart"] = ["PAL"]
	if has_rca:
		modes["RCA"] = ["576i", "PAL"]
	if has_avjack:
		modes["Jack"] = ["PAL", "NTSC", "Multi"]

	modes["HDMI"] = ["720p", "1080p", "1080i", "576p", "576i", "480p", "480i"]
	widescreen_modes = {"720p", "1080p", "1080i"}

	modes["HDMI-PC"] = ["PC"]

	if has_yuv:
		modes["YPbPr"] = modes["HDMI"]

	if "YPbPr" in modes and not has_yuv:
		del modes["YPbPr"]

	if "Scart" in modes and not has_scart and (has_rca or has_avjack):
		modes["RCA"] = modes["Scart"]
		del modes["Scart"]

	if "Scart" in modes and not has_rca and not has_scart and not has_avjack:
		del modes["Scart"]

	def getOutputAspect(self):
		ret = (16, 9)
		port = config.av.videoport.value
		if port not in config.av.videomode:
			print("[VideoHardware] Current port not available in getOutputAspect!!! force 16:9")
		else:
			mode = config.av.videomode[port].value
			force_widescreen = self.isWidescreenMode(port, mode)
			is_widescreen = force_widescreen or config.av.aspect.value in ("16_9", "16_10")
			is_auto = config.av.aspect.value == "auto"
			if is_widescreen:
				if force_widescreen:
					pass
				else:
					aspect = {"16_9": "16:9", "16_10": "16:10"}[config.av.aspect.value]
					if aspect == "16:10":
						ret = (16, 10)
			elif is_auto:
				if isfile("/proc/stb/vmpeg/0/aspect"):
					try:
						aspect_str = open("/proc/stb/vmpeg/0/aspect", "r").read()
						if aspect_str == "1": # 4:3
							ret = (4, 3)
					except IOError:
						print("[VideoHardware] Read /proc/stb/vmpeg/0/aspect failed!")
			else:  # 4:3
				ret = (4, 3)
		return ret

	def __init__(self):
		self.last_modes_preferred = []
		self.on_hotplug = CList()
		self.current_mode = None
		self.current_port = None

		self.readAvailableModes()
		self.readPreferredModes()

		if "HDMI-PC" in self.modes and not self.getModeList("HDMI-PC"):
			print("[VideoHardware] Remove HDMI-PC because of not existing modes")
			del self.modes["HDMI-PC"]
		if "Scart" in self.modes and not self.getModeList("Scart"):
			print("[VideoHardware] Remove Scart because of not existing modes")
			del self.modes["Scart"]
		if "YPbPr" in self.modes and not has_yuv:
			del self.modes["YPbPr"]
		if "Scart" in self.modes and not has_scart and (has_rca or has_avjack):
			modes["RCA"] = modes["Scart"]
			del self.modes["Scart"]
		if "Scart" in self.modes and not has_rca and not has_scart and not has_avjack:
			del self.modes["Scart"]

		self.createConfig()

		# take over old AVSwitch component :)
		from Components.AVSwitch import AVSwitch
		config.av.aspectratio.notifiers = []
		config.av.tvsystem.notifiers = []
		config.av.wss.notifiers = []
		AVSwitch.getOutputAspect = self.getOutputAspect

		config.av.colorformat_hdmi = ConfigSelection(choices={"hdmi_rgb": _("RGB"), "hdmi_yuv": _("YUV"), "hdmi_422": _("422")}, default="hdmi_rgb")
		config.av.colorformat_yuv = ConfigSelection(choices={"yuv": _("YUV")}, default="yuv")
		config.av.hdmi_audio_source = ConfigSelection(choices={"pcm": _("PCM"), "spdif": _("SPDIF")}, default="pcm")
		config.av.threedmode = ConfigSelection(choices={"off": _("Off"), "sbs": _("Side by Side"), "tab": _("Top and Bottom")}, default="off")
		config.av.threedmode.addNotifier(self.set3DMode)
		config.av.colorformat_hdmi.addNotifier(self.setHDMIColor)
		config.av.colorformat_yuv.addNotifier(self.setYUVColor)
		config.av.hdmi_audio_source.addNotifier(self.setHDMIAudioSource)

		config.av.aspect.addNotifier(self.updateAspect)
		config.av.wss.addNotifier(self.updateAspect)
		config.av.policy_43.addNotifier(self.updateAspect)
		if hasattr(config.av, 'policy_169'):
			config.av.policy_169.addNotifier(self.updateAspect)

	def readAvailableModes(self):
		try:
			modes = open("/proc/stb/video/videomode_choices").read()[:-1]
		except IOError:
			print("[VideoHardware] Read /proc/stb/video/videomode_choices failed!")
			self.modes_available = []
			return
		self.modes_available = modes.split(' ')

	def readPreferredModes(self):
		if config.av.edid_override.value == False:
			if isfile("/proc/stb/video/videomode_preferred"):
				modes = open("/proc/stb/video/videomode_preferred").read()[:-1]
				self.modes_preferred = modes.split(' ')
				print("[VideoHardware] Reading preferred modes: ", self.modes_preferred)
			elif isfile("/proc/stb/video/videomode_edid"):
				modes = open("/proc/stb/video/videomode_edid").read()[:-1]
				self.modes_preferred = modes.split(' ')
				print("[VideoHardware] Reading edid modes: ", self.modes_preferred)
			else:
				self.modes_preferred = self.modes_available
			if len(self.modes_preferred) <= 1:
				self.modes_preferred = self.modes_available
				print("[VideoHardware] Reading preferred modes is empty, using all video modes")
		else:
			self.modes_preferred = self.modes_available
			print("[VideoHardware] edid_override enabled, using all video modes")
		self.last_modes_preferred = self.modes_preferred

	# check if a high-level mode with a given rate is available.
	def isModeAvailable(self, port, mode, rate):
		rate = self.rates[mode][rate]
		for mode in rate.values():
			if port != "HDMI":
				if mode not in self.modes_preferred:
					return False
			else:
				if mode not in self.modes_available:
					return False
		return True

	def isWidescreenMode(self, port, mode):
		return mode in self.widescreen_modes

	def setMode(self, port, mode, rate):
		force = config.av.force.value
		print("[VideoHardware] setMode - port:", port, "mode:", mode, "rate:", rate, "force:", force)
		# we can ignore "port"
		self.current_mode = mode
		self.current_port = port
		modes = self.rates[mode][rate]

		mode_23 = modes.get(23)
		mode_24 = modes.get(24)
		mode_25 = modes.get(25)
		mode_29 = modes.get(29)
		mode_30 = modes.get(30)
		mode_50 = modes.get(50)
		mode_59 = modes.get(59)
		mode_60 = modes.get(60)

		if mode_50 is None or force == 60:
			mode_50 = mode_60
		if mode_59 is None or force == 50:
			mode_59 = mode_50
		if mode_60 is None or force == 50:
			mode_60 = mode_50

		if mode_23 is None or force:
			mode_23 = mode_60
			if force == 50:
				mode_23 = mode_50
		if mode_24 is None or force:
			mode_24 = mode_60
			if force == 50:
				mode_24 = mode_50
		if mode_25 is None or force:
			mode_25 = mode_60
			if force == 50:
				mode_25 = mode_50
		if mode_29 is None or force:
			mode_29 = mode_60
			if force == 50:
				mode_29 = mode_50
		if mode_30 is None or force:
			mode_30 = mode_60
			if force == 50:
				mode_30 = mode_50

		if mode_50 is not None:
			try:
				open("/proc/stb/video/videomode_50hz", "w").write(mode_50)
			except IOError:
				print("[VideoHardware] Write to /proc/stb/video/videomode_50hz failed!")
				if isfile("/proc/stb/video/videomode"):
					try:
						# fallback if no possibility to setup 50 hz mode
						open("/proc/stb/video/videomode", "w").write(mode_50)
					except IOError:
						print("[VideoHardware] Write to /proc/stb/video/videomode failed!")

		if mode_60 is not None:
			try:
				open("/proc/stb/video/videomode_60hz", "w").write(mode_60)
			except IOError:
				print("[VideoHardware] Write to /proc/stb/video/videomode_60hz failed!")

		if Has24hz and mode_24 is not None:
			try:
				open("/proc/stb/video/videomode_24hz", "w").write(mode_24)
			except IOError:
				print("[VideoHardware] Write to /proc/stb/video/videomode_24hz failed!")

		#call setResolution() with -1,-1 to read the new scrren dimesions without changing the framebuffer resolution
		from enigma import gMainDC
		gMainDC.getInstance().setResolution(-1, -1)

		self.updateAspect(None)
		self.updateColor(port)

	def saveMode(self, port, mode, rate):
		print("[VideoHardware] saveMode", port, mode, rate)
		config.av.videoport.value = port
		config.av.videoport.save()
		if port in config.av.videomode:
			config.av.videomode[port].value = mode
			config.av.videomode[port].save()
		if mode in config.av.videorate:
			config.av.videorate[mode].value = rate
			config.av.videorate[mode].save()

	def isPortAvailable(self, port):
		# fixme
		return True

	def isPortUsed(self, port):
		if port == "HDMI":
			self.readPreferredModes()
			return len(self.modes_preferred) != 0
		else:
			return True

	def getPortList(self):
		return [port for port in self.modes if self.isPortAvailable(port)]

	# get a list with all modes, with all rates, for a given port.
	def getModeList(self, port):
		print("[VideoHardware] getModeList for port", port)
		res = []
		for mode in self.modes[port]:
			# list all rates which are completely valid
			rates = [rate for rate in self.rates[mode] if self.isModeAvailable(port, mode, rate)]

			# if at least one rate is ok, add this mode
			if len(rates):
				res.append((mode, rates))
		return res

	def createConfig(self, *args):
		lst = []

		config.av.videomode = ConfigSubDict()
		config.av.videorate = ConfigSubDict()

		# create list of output ports
		portlist = self.getPortList()
		for port in portlist:
			descr = port
			if descr == "Scart" and has_rca and not has_scart:
				descr = "RCA"
			if descr == "Scart" and has_avjack and not has_scart:
				descr = "Jack"
			lst.append((port, descr))

			# create list of available modes
			modes = self.getModeList(port)
			if len(modes):
				config.av.videomode[port] = ConfigSelection(choices=[mode for (mode, rates) in modes])
			for (mode, rates) in modes:
				ratelist = []
				for rate in rates:
					if rate == "auto" and not Has24hz:
						continue
					ratelist.append((rate, rate))
				config.av.videorate[mode] = ConfigSelection(choices=ratelist)
		config.av.videoport = ConfigSelection(choices=lst)

	def setConfiguredMode(self):
		port = config.av.videoport.value
		if port not in config.av.videomode:
			print("[VideoHardware] Current port not available, not setting videomode")
			return

		mode = config.av.videomode[port].value

		if mode not in config.av.videorate:
			print("[VideoHardware] Current mode not available, not setting videomode")
			return

		rate = config.av.videorate[mode].value
		self.setMode(port, mode, rate)

	def updateAspect(self, cfgelement):
		port = config.av.videoport.value
		if port not in config.av.videomode:
			print("[VideoHardware] Current port not available, not setting videomode")
			return
		mode = config.av.videomode[port].value
		aspect = config.av.aspect.value

		if not config.av.wss.value:
			wss = "auto(4:3_off)"
		else:
			wss = "auto"

		policy = config.av.policy_43.value
		if hasattr(config.av, 'policy_169'):
			policy2 = config.av.policy_169.value
			print("[VideoHardware] -> setting aspect, policy, policy2, wss", aspect, policy, policy2, wss)
		else:
			print("[VideoHardware] -> setting aspect, policy, wss", aspect, policy, wss)

		if isfile("/proc/stb/video/aspect"):
			try:
				open("/proc/stb/video/aspect", "w").write(aspect)
			except IOError:
				print("[VideoHardware] Write to /proc/stb/video/aspect failed!")
		if isfile("/proc/stb/video/policy"):
			try:
				open("/proc/stb/video/policy", "w").write(policy)
			except IOError:
				print("[VideoHardware] Write to /proc/stb/video/policy failed!")
		if isfile("/proc/stb/denc/0/wss"):
			try:
				open("/proc/stb/denc/0/wss", "w").write(wss)
			except IOError:
				print("[VideoHardware] Write to /proc/stb/denc/0/wss failed!")
		if isfile("/proc/stb/video/policy2") and hasattr(config.av, 'policy_169'):
			try:
				open("/proc/stb/video/policy2", "w").write(policy2)
			except IOError:
				print("[VideoHardware] Write to /proc/stb/video/policy2 failed!")

	def set3DMode(self, configElement):
		try:
			open("/proc/stb/video/3d_mode", "w").write(configElement.value)
		except:
			print("[VideoHardware] Write to /proc/stb/video/3d_mode failed!")

	def setHDMIAudioSource(self, configElement):
		try:
			open("/proc/stb/hdmi/audio_source", "w").write(configElement.value)
		except:
			print("[VideoHardware] Write to /proc/stb/hdmi/audio_source failed!")

	def setHDMIColor(self, configElement):
		map = {"hdmi_rgb": 0, "hdmi_yuv": 1, "hdmi_422": 2}
		try:
			open("/proc/stb/avs/0/colorformat", "w").write(configElement.value)
		except:
			print("[VideoHardware] Write to /proc/stb/avs/0/colorformat failed!")

	def setYUVColor(self, configElement):
		map = {"yuv": 0}
		try:
			open("/proc/stb/avs/0/colorformat", "w").write(configElement.value)
		except:
			print("[VideoHardware] Write to /proc/stb/avs/0/colorformat failed!")

	def updateColor(self, port):
		print("[VideoHardware] updateColor: ", port)
		if port == "HDMI":
			self.setHDMIColor(config.av.colorformat_hdmi)
		elif port == "YPbPr" and has_yuv:
			self.setYUVColor(config.av.colorformat_yuv)
		elif port == "Scart" and has_scart:
			map = {"cvbs": 0, "rgb": 1, "svideo": 2, "yuv": 3}
			from enigma import eAVSwitch
			eAVSwitch.getInstance().setColorFormat(map[config.av.colorformat.value])


video_hw = VideoHardware()
video_hw.setConfiguredMode()
