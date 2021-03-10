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
		self.__scan_memory()

	def __scan_memory(self):
		"""
		This is currently inefficient due to single byte scanning. TODO make
		faster.

		Explanation of memory search:

		Step 1: Scan memory for the follow pattern:
			- 48 8b 05 xx xx xx xx 48 39 48 68 0f 94 c0 c3
		step 2: The address, namely A, is our starting address that starts with
			this pattern.
		step 3: Use B = A + read(A + 3) + 7 as our base address to follow.
		step 4: Let C = read(B) + 0x68
		step 5: Let D = read(C) + 0x3e8
		Step 6: Health location is at D, health value is read(D)
		"""
		game = self.__game
		part1 = '488b05'
		part2 = '483948680f94c0c3'
		address = 0x140000000 - 0x4
		found = False

		def p1_check(address):
			value = game.read_bytes(address, 3)
			return part1 == value.hex()

		def p2_check(address):
			value = game.read_bytes(address + 7, 8)
			return value.hex() == part2


		while not found:
			address += 4
			c1 = p1_check(address)
			
			if c1:
				c2 = p2_check(address)
			
			found = c1 and c2


		self.__base_addr = address
		self.__base_addr = address + game.read_int(address + 3) + 7

	@property
	def __health_address(self):
		addr = self.__base_addr
		temp = self.__game.read_int(addr) + 0x68
		temp2 = self.__game.read_int(temp) + 0x3e8
		return temp2

	def get_health(self):
		
		return self.__game.read_int(self.__health_address)

	def set_health(self, value):
		self.__game.write_int(self.__health_address, value)

class Window:
	def __init__(self):
		# public fields to be edited by threads
		self.active_server = False
		self.active_client = False

		self.__window = tk.Tk()
		self.__font   = font.Font(size=24)

		
		self.__server_frame()
		self.__client_frame()

		self.__window.protocol("WM_DELETE_WINDOW", self.onclose)
		
	def onclose(self):
		self.active_client = False
		self.active_server = False
		self.__window.destroy()


	def __client_frame(self):
		cframe = tk.Frame(self.__window)
		cframe.pack(side=tk.RIGHT, anchor=tk.NE)

		ipframe = tk.Frame(cframe)
		ipframe.grid(row=2, column=0)
		# Connection information:
		# Entry for IP Address
		self.__ipentry = tk.Entry(ipframe, width=10, font=self.__font)
		self.__ipentry.grid(row=0, column=1)
		self.__ipentry.insert(0, "localhost")

		iplabel = tk.Label(ipframe, text="IP: ", font=self.__font)
		iplabel.grid(row=0, column=0)

		# Client connection button
		self.__cn_button = tk.Button(
			cframe,
			text="Connect to IP",
			width=12,
			command=self.client_connect, 
			font=self.__font)
		self.__cn_button.grid(row=0, column=0)

		# Client disconnect button
		self.__dn_button = tk.Button(
			cframe,
			text="Disconnect", 
			width=12,
			command=self.client_disconnect, 
			font=self.__font)
		self.__dn_button.grid(row=1, column=0)

		iplabel = tk.Label(cframe, text="Client Output: ", font=self.__font)
		iplabel.grid(row=3, column=0)

		self.__infobox_client = tk.Text(cframe, width=30,height=15)
		self.__infobox_client.grid(row=4, column=0)
		

	def __server_frame(self):
		sframe = tk.Frame(self.__window)
		sframe.pack(side=tk.LEFT, anchor=tk.NW)

		# Button to start the server.
		self.__sv_cn = tk.Button(
			sframe,
			text="Host Server",
			width=12,
			command=self.handle_host, 
			font=self.__font)
		self.__sv_cn.grid(row=0, column=0)

		# Button to kill current server.
		self.__sv_dn = tk.Button(
			sframe,
			text="Kill Server",
			width=12,
			command=self.end_host, font=self.__font)
		self.__sv_dn.grid(row=1, column=0)

		iplabel = tk.Label(sframe, text="Server Output: ", font=self.__font)
		iplabel.grid(row=3, column=0)

		# Just to make it look nice
		emptylabel = tk.Label(sframe, text="", font=self.__font)
		emptylabel.grid(row=2, column=0)

		# Create output textbox for information.
		self.__infobox_serv = tk.Text(sframe, width=30,height=15)
		self.__infobox_serv.grid(row=4, column=0)


	def run(self):
		self.__window.mainloop()

	# Simple Logger output
	def logger_client(self, output):
		self.__infobox_client.insert(tk.END, output + "\n")

	def logger_server(self, output):
		self.__infobox_serv.insert(tk.END, output + "\n")

	# Called when client is disconnected by GUI.
	def client_disconnect(self):
		self.active_client = False
		self.__cn_button['state'] = 'normal'


	def __set_active_client(self, act):
		self.active_client = act
		if act:
			self.__cn_button['state'] = 'disabled'
		else:
			self.__cn_button['state'] = 'normal'

	# Handles creating a client thread.
	def client_connect(self):
		if self.active_client:
			self.logger_client("Client is already active.")
		else:
			def client_thread():
				ip = self.__ipentry.get()
				self.active_client = True
				try:
					client = Client(
						ip, 
						PORT, 
						active_info=self, 
						logger=self.logger_client)
				except Exception as ex:
					self.logger_client(str(ex))
					self.__set_active_client(False)

				self.run_loop(client, error=on_err)
				self.active_client = False


			def on_err():
				self.__cn_button['state'] = 'normal'

			

			t  = thr.Thread(target=lambda: client_thread())
			t.start()
			self.__cn_button['state'] = 'disabled'

	# Called when the start server button is pressed.
	def handle_host(self):
		def on_err():
			self.__sv_cn['state'] = 'normal'

		self.active_server = True
		server = Server(active_info=self, logger=self.logger_server)
		t = thr.Thread(target=lambda: self.run_loop(server, error=on_err))
		t.start()
		self.__sv_cn['state'] = 'disabled'

	def end_host(self):
		self.active_server = False
		self.__sv_cn['state'] = 'normal'

	def run_loop(self, obj, error=lambda: None):
		try:
			obj.run()
		except Exception as ex:
			self.logger_client(f"ERROR: {ex}" )
			error()


		


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
