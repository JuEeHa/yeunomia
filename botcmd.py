import threading

class Nick:
	def __init__(self, *, nick, channels = None, user = None):
		if channels is None: channels = set()

		self.nick = nick
		self.channels = channels
		self.user = user

	def __repr__(self):
		if self.__module__ == '__main__':
			name = 'Nick'
		else:
			name = self.__module__ + '.Nick'

		return '%s(nick = %s, channels = %s, user = %s)' % (name, self.nick, self.channels, self.user)

# {b'nick1': Nick(...), ...}
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

	# Split the commands into the command itself and the argument. Remove additional whitespace around them
	command, _, argument = (i.strip() for i in command.partition(' '))

	if command == 'nicks':
		with nicks_dict_lock:
			print('key', 'nick', 'user', 'channels', sep = '\t')

			for nick in nicks_dict:
				nick_object = nicks_dict[nick]
				print(nick, nick_object.nick, nick_object.user, nick_object.channels, sep = '\t')

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

def add_nick_to_channel(nick, channel, *, already_on_channel_acceptable = False):
	global nicks_dict_lock, nicks_dict

	nick = bytes(nick) #Ensure nick is hashable
	channel = bytes(channel) #Ensure channel is hashable

	with nicks_dict_lock:
		if nick not in nicks_dict:
			nicks_dict[nick] = Nick(nick = nick)

		assert already_on_channel_acceptable or channel not in nicks_dict[nick].channels

		nicks_dict[nick].channels.add(channel)

def remove_nick_from_channel(nick, channel):
	global nicks_dict_lock, nicks_dict

	nick = bytes(nick) #Ensure nick is hashable
	channel = bytes(channel) #Ensure channel is hashable

	with nicks_dict_lock:
		nicks_dict[nick].channels.remove(channel)

		# If we can no longer track the nick, null the user field
		# This is because next time we see this nick, it might be a different person
		if len(nicks_dict[nick].channels) == 0:
			nicks_dict[nick].user = None

def rename_nick(old_nick, new_nick):
	global nicks_dict_lock, nicks_dict

	old_nick = bytes(old_nick) #Ensure old_nick is hashable
	new_nick = bytes(new_nick) #Ensure new_nick is hashable

	with nicks_dict_lock:
		assert nicks_dict[old_nick].nick == old_nick
		assert new_nick not in nicks_dict

		nick_object = nicks_dict.pop(old_nick)
		nick_object.nick = new_nick
		nicks_dict[new_nick] = nick_object

		assert old_nick not in nicks_dict

def quit_nick(nick):
	global nicks_dict_lock, nicks_dict

	nick = bytes(nick) #Ensure nick is hashable

	with nicks_dict_lock:
		# Clear channes
		nicks_dict[nick].channels = set()

		# Null user field, because the next time we see this nick, it might be a different person
		nicks_dict[nick].user = None

# handle_nonmessage(*, prefix, command, arguments, irc)
# Called for all other commands than PINGs and PRIVMSGs.
# prefix is the prefix at the start of the message, without the leading ':'
# command is the command or number code
# arguments is rest of the arguments of the command, represented as a list. ':'-arguments are handled automatically
# irc is the IRC API object
# All strings are bytestrings or bytearrays
def handle_nonmessage(*, prefix, command, arguments, irc):
	global nicks_dict_lock, nicks_dict

	# FIXME: If we leave a channel, remove information pertaining to it from nicks database

	if command == b'353': # Nick listing
		_, _, channel, channel_nicks = arguments

		own_nick = irc.get_nick()

		for nick in channel_nicks.split(b' '):
			# Remove signifiers of opness / voicedness
			if nick[0:1] in (b'@', b'+'):
				nick = nick[1:]

			add_nick_to_channel(nick, channel, already_on_channel_acceptable = True)

	elif command == b'JOIN':
		nick = prefix.partition(b'!')[0]
		channel, = arguments

		add_nick_to_channel(nick, channel)

	elif command == b'PART':
		nick = prefix.partition(b'!')[0]
		channel, = arguments

		remove_nick_from_channel(nick, channel)

	elif command == b'NICK':
		old_nick = prefix.partition(b'!')[0]
		new_nick, = arguments

		rename_nick(old_nick, new_nick)

	elif command == b'QUIT':
		nick = prefix.partition(b'!')[0]

		quit_nick(nick)

	elif command == b'KICK':
		channel, nick, _ = arguments

		remove_nick_from_channel(nick, channel)
