import os
import socket
import time
import pymem

import threading    as thr
import tkinter      as tk
import tkinter.font as font

# Program name to search for.
PROGRAM = 'DarkSoulsIII.exe'
PROGRAM = "DarkSoulsRemastered.exe"
BASE_PATTERN = b"\x48\x8b\x05....\x48\x39\x48\x68\x0f\x94\xc0\xc3"

# Port for this mod: Blaze it nicely.
PORT = 42069
# Time out used for socket reading; Prevents locking operations.
TIMEOUT = 0.01

class Server:
	def __init__(self, active_info=None,logger=print):
		# The connections to track
		self.__connections = []
		self.__logger      = logger

		# General server socket to listen for connections.
		self.__listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.__listen.settimeout(0.15)
		self.__listen.bind(('', 42069))
		self.__listen.listen(1)

		self.__active_trigger = active_info

		self.__logger("Starting server")

	@property
	def still_connected(self):
		if self.__active_trigger is None:
			return True
		else:
			return self.__active_trigger.active_server
	
	def check_connections(self):
		try:
			#print(f'Listening for connection for player: {len(self.__connections)+1}')
			conn, _ = self.__listen.accept()
			self.__connections.append(conn)
			conn.settimeout(TIMEOUT)
			self.__logger(f'Received Player {len(self.__connections)}')
		except socket.timeout:
			pass

	def run(self):
		while self.still_connected:
			self.check_connections()
			disconnected = []			
			
			for i, player in enumerate(self.__connections):
				try:
					info = player.recv(1024).splitlines()
					if len(info) == 0:
						disconnected.append(i)
					else:
						for dmg in info:
							for k, p2 in enumerate(self.__connections):
								if i != k:						
									p2.sendall((dmg.decode() + '\n').encode())
				except socket.timeout:
					info = []

			for i in disconnected:
				del self.__connections[i]
				self.__logger(f'Player {i+1} disconnected')
			# Sleep for a short a little less than a frame.
			time.sleep(0.015)
		self.__logger("Server shutting down")



class Client:
	def __init__(self, address, port, active_info=None, logger=print):
		logger("scanning memory")
		self.__memory         = Memory()
		logger("Found health values.")
		self.__cur_health     = 1
		self.__prev_dmg       = 1000
		self.__active_trigger = active_info
		self.__logger         = logger



		self.__logger('Attempting to connect to server')
		self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.__socket.connect((address, port))

		self.__logger('Connected to server.')
		self.__socket.settimeout(TIMEOUT)




	@property
	def still_connected(self):
		server_live = self.__prev_dmg > 0
		
		if self.__active_trigger is None:
			return server_live
		else:
			local_live  = self.__active_trigger.active_client
			return  local_live and server_live

	@property
	def health(self):
		try:			
			return self.__memory.get_health()
		except:
			# This will happen from time to time as pointers are updated.
			return 1

	def send_damage(self):
		cur_health = self.health
		if cur_health < self.__cur_health:
			self.__socket.sendall((str(self.__cur_health - cur_health) + '\n').encode())

		self.__cur_health = cur_health

	def recv_damage(self):
		try:
			msg = self.__socket.recv(1024).splitlines()
			dmg = sum(map(lambda x: int(x.decode()), msg))
			new_health = max(self.health - dmg, 0)
			#self.__game.write_int(self.__cur_address, new_health)
			self.__memory.set_health(new_health)
			self.__cur_health = new_health
			self.__logger(f'Received {dmg}.')
			self.__prev_dmg = dmg
		except:
			pass

	def run(self):
		while self.still_connected:
			time.sleep(0.015)
			self.send_damage()
			self.recv_damage()
		

class Memory:
	def __init__(self):
		self.__game = pymem.Pymem(PROGRAM)
		self.__base__addr = self.__init_base_addr()
		self.__scan_memory()

	@property
	def hp(self):
		addr = self.__game.read_int(self.__base_addr) + 0x68
		addr = self.__game.read_int(addr) + 0x3e8
		return 	self.__game.read_int(addr)

	@hp.setter
	def hp(self, value):
		addr = self.__game.read_int(self.__base_addr) + 0x68
		addr = self.__game.read_int(addr) + 0x3e8
		self.__game.write_int(addr, value)
	

	def __init_base_addr(self):
		base = self.__game.pattern_scan_all(BASE_PATTERN)
		return base + self.__game.read_int(base + 3) + 7

	def get_health(self):		
		return self.__game.read_int(self.__health_address)

	def set_health(self, value):
		self.__game.write_int(self.__health_address, value)



if __name__ == '__main__':
	import sys
	if 'connect' in sys.argv:
		address = sys.argv[2]
		Client(address, 42069).run()
	elif 'client' in sys.argv:
		Client('localhost', 42069).run()
	elif 'server' in sys.argv:
		Server().run()
	elif 'gui' in sys.argv:
		Window().run()
	else:
		Window().run()
