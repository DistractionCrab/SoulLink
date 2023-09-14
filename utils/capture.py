import cv2
import win32gui
import win32ui
import win32con
import win32api
import numpy as np
import dxcam
import time

class WindowCapture:

	# properties
	w = 0
	h = 0
	hwnd = None
	cropped_x = 0
	cropped_y = 0
	offset_x = 0
	offset_y = 0

	# constructor
	def __init__(self, window_name):
		# find the handle for the window we want to capture
		self.hwnd = win32gui.FindWindow(None, window_name)
		if not self.hwnd:
			raise Exception('Window not found: {}'.format(window_name))

		# get the window size
		window_rect = win32gui.GetWindowRect(self.hwnd)
		self.w = window_rect[2] - window_rect[0]
		self.h = window_rect[3] - window_rect[1]

		# account for the window border and titlebar and cut them off
		border_pixels = 8
		titlebar_pixels = 30
		self.w = self.w - (border_pixels * 2)
		self.h = self.h - titlebar_pixels - border_pixels
		self.cropped_x = border_pixels
		self.cropped_y = titlebar_pixels

		# set the cropped coordinates offset so we can translate screenshot
		# images into actual screen positions
		self.offset_x = window_rect[0] + self.cropped_x
		self.offset_y = window_rect[1] + self.cropped_y

	@property
	def rect(self):
		return win32gui.GetWindowRect(self.hwnd)
	
	@property
	def width(self):
		return self.w
	
	@property
	def height(self):
		return self.h
	

	def capture(self):

		# get the window image data
		wDC = win32gui.GetWindowDC(self.hwnd)
		dcObj = win32ui.CreateDCFromHandle(wDC)
		cDC = dcObj.CreateCompatibleDC()
		dataBitMap = win32ui.CreateBitmap()
		dataBitMap.CreateCompatibleBitmap(dcObj, self.w, self.h)
		cDC.SelectObject(dataBitMap)
		cDC.BitBlt((0, 0), (self.w, self.h), dcObj, (self.cropped_x, self.cropped_y), win32con.SRCCOPY)

		# convert the raw data into a format opencv can read
		#dataBitMap.SaveBitmapFile(cDC, 'debug.bmp')
		signedIntsArray = dataBitMap.GetBitmapBits(True)
		img = np.fromstring(signedIntsArray, dtype='uint8')
		img.shape = (self.h, self.w, 4)

		# free resources
		dcObj.DeleteDC()
		cDC.DeleteDC()
		win32gui.ReleaseDC(self.hwnd, wDC)
		win32gui.DeleteObject(dataBitMap.GetHandle())

		img = img[...,:3]
		img = np.ascontiguousarray(img)

		return img

	def click_prop(self, x, y):
		x = min(max(0, x), 1)*self.width
		y = min(max(0, y), 1)*self.height

		self.click(int(x), int(y))

	def click(self, x, y):
		print(f"clicking at {(x, y)}")
		lp = win32api.MAKELONG(x, y)

		win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
		win32api.SendMessage(self.hwnd, win32con.WM_LBUTTONUP, None, lp)

	def test_stream(self):
		s = 0
		ct = 0
		try:
			while True:
				t0 = time.time()
				i = self.capture()
				s += 1/(time.time() - t0)

				ct += 1
				if ct % 60 == 0:
					print(f"fps: {s/60}")
					s = 0
					ct = 0
				
				if i is not None:
					cv2.imshow('Computer Vision', i)

					if cv2.waitKey(1) == ord('q'):
						cv2.destroyAllWindows()
						break
		except Exception as ex:
			print(ex)
			cv2.destroyAllWindows()