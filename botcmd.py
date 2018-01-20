import threading

# {b'#channel': {b'nick1', b'nick2', …}, …}
nicks_dict = {}
nicks_dict_lock = threading.Lock()

# initialize(*, config)
# Called to initialize the IRC bot
# Runs before even logger is brought up, and blocks further bringup until it's done
# config is a configpatser.ConfigParser object containig contents of bot.conf
def initialize(*, config):
	pass

# on_connect(*, irc)
# Called after IRC bot has connected and sent the USER/NICk commands but not yet attempted anything else
# Blocks the bot until it's done, including PING/PONG handling
# irc is the IRC API object
def on_connect(*, irc):
	global nicks_dict, nicks_dict_lock
	with nicks_dict_lock:
		nicks_dict = {}

# on_quit(*, irc)
# Called just before IRC bot sends QUIT
# Blocks the bot until it's done, including PING/PONG handling
# irc is the IRC API object
def on_quit(*, irc):
	pass

def handle_command(command, channel, *, response_prefix, irc):
	global nicks_dict, nicks_dict_lock

	channel = bytes(channel) #Ensure channel is hashable

	# Split the commands into the command itself and the argument. Remove additional whitespace around them
	command, _, argument = (i.strip() for i in command.partition(' '))

	if command == 'nicks':
		with nicks_dict_lock:
			response = bytearray()

			for nick in nicks_dict[channel]:
				nick_utf8 = nick.decode('utf-8')
				nick_zwsp = nick_utf8[0] + '\u200b' + nick_utf8[1:]
				nick = nick_zwsp.encode('utf-8')

				response.extend(nick + b' ')

				# Send every 300 bytes
				if len(response) >= 300:
					irc.bot_response_bytes(channel, response_prefix + response)
					response = bytearray()

			if len(response) > 0:
				irc.bot_response_bytes(channel, response_prefix + response)

	else:
		irc.bot_response_bytes(channel, response_prefix + 'Commands: nicks'.encode('utf-8'))

# handle_message(*, prefix, message, nick, channel, irc)
# Called for PRIVMSGs.
# prefix is the prefix at the start of the message, without the leading ':'
# message is the contents of the message
# nick is who sent the message
# channel is where you should send the response (note: in queries nick == channel)
# irc is the IRC API object
# All strings are bytestrings or bytearrays
def handle_message(*, prefix, message, nick, channel, irc):
	own_nick = irc.get_nick()

	# Run a command if it's prefixed with our nick we're in a query
	# In queries, nick (who sent) and channel (where to send) are the same
	if message[:len(own_nick) + 1].lower() == own_nick.lower() + b':' or nick == channel:
		if message[:len(own_nick) + 1].lower() == own_nick.lower() + b':':
			command = message[len(own_nick) + 1:].strip()
			response_prefix = nick + b': '

		else:
			command = message
			response_prefix = b''

		command = command.decode(encoding = 'utf-8', errors = 'replace')

		response = handle_command(command, channel, response_prefix = response_prefix, irc = irc)


# handle_nonmessage(*, prefix, command, arguments, irc)
# Called for all other commands than PINGs and PRIVMSGs.
# prefix is the prefix at the start of the message, without the leading ':'
# command is the command or number code
# arguments is rest of the arguments of the command, represented as a list. ':'-arguments are handled automatically
# irc is the IRC API object
# All strings are bytestrings or bytearrays
def handle_nonmessage(*, prefix, command, arguments, irc):
	global nicks_dict_lock, nicks_dict

	if command == b'353': # Nick listing
		_, _, channel, channel_nicks = arguments

		channel = bytes(channel) # Ensure channel is hashable

		with nicks_dict_lock:
			if channel not in nicks_dict:
				nicks_dict[channel] = set()

			for nick in channel_nicks.split(b' '):
				nick = bytes(nick) #Ensure nick is hashable

				# Remove prefixes from nicks
				if nick[0:1] == b'@' or nick[0:1] == b'+':
					nick = nick[1:]

				nicks_dict[channel].add(nick)

	elif command == b'JOIN':
		nick = prefix.partition(b'!')[0]
		channel, = arguments

		nick = bytes(nick) #Ensure nick is hashable
		channel = bytes(channel) # Ensure channel is hashable

		with nicks_dict_lock:
			if channel not in nicks_dict:
				nicks_dict[channel] = set()

			nicks_dict[channel].add(nick)

	elif command == b'PART':
		nick = prefix.partition(b'!')[0]
		channel, = arguments

		nick = bytes(nick) #Ensure nick is hashable
		channel = bytes(channel) # Ensure channel is hashable

		with nicks_dict_lock:
			nicks_dict[channel].remove(nick)

	elif command == b'NICK':
		old_nick = prefix.partition(b'!')[0]
		new_nick, = arguments

		# Ensure nicks are hashable
		old_nick = bytes(old_nick)
		new_nick = bytes(new_nick)

		with nicks_dict_lock:
			for channel in nicks_dict:
				if old_nick in nicks_dict[channel]:
					nicks_dict[channel].remove(old_nick)
					nicks_dict[channel].add(new_nick)

	elif command == b'QUIT':
		nick = prefix.partition(b'!')[0]

		nick = bytes(nick) #Ensure nick is hashable

		with nicks_dict_lock:
			for channel in nicks_dict:
				if nick in nicks_dict[channel]:
					nicks_dict[channel].remove(nick)

	elif command == b'KICK':
		channel, nick, _ = arguments

		nick = bytes(nick) #Ensure nick is hashable
		channel = bytes(channel) # Ensure channel is hashable

		with nicks_dict_lock:
			nicks_dict[channel].remove(nick)
