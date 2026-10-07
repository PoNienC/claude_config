"""
Copyright 2019 Meta Berghauser Pont

This file is part of PST.

PST is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version. The GNU Lesser General Public License
is intended to guarantee your freedom to share and change all versions
of a program--to make sure it remains free software for all its users.

PST is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with PST. If not, see <http://www.gnu.org/licenses/>.
"""


class AnalysisDelegate(object):
	def setProgress(self, progress):
		pass

	def setStatus(self, text):
		pass

	def getCancel(self):
		pass


import time
class AnalysisDelegateFilter(object):
	def __init__(self, delegate, min_interval_sec=0.1):
		self._delegate = delegate
		self._minIntervalSec = min_interval_sec
		self._tsLastUpdate = -1
		# DEBUG
		self._statusText = None
		self._tsLastStatus = -1
		# DEBUG

	def outputStats(self):
		pass

	# AnalysisDelegate interface
	def setProgress(self, progress):
		if self._testFrequencyFilter():
			self._delegate.setProgress(progress)

	# AnalysisDelegate interface
	def setStatus(self, text):
		# DEBUG
		ts = time.perf_counter()
		if self._statusText:
			print("%s (%.3f sec)" % (self._statusText, ts - self._tsLastStatus))
		self._statusText = text
		self._tsLastStatus = ts
		# DEBUG

		self._delegate.setStatus(text)
		self._resetFrequencyFilter()

	# AnalysisDelegate interface
	def getCancel(self):
		return self._delegate.getCancel()

	def _resetFrequencyFilter(self):
		self._tsLastUpdate = -1

	def _testFrequencyFilter(self):
		ts = time.perf_counter()
		if ts - self._tsLastUpdate < self._minIntervalSec:
			return False
		self._tsLastUpdate = ts;
		return True