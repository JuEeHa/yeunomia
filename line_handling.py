import constants

class API:
	def __init__(self, serverthread_object):
		# We need to access the internal functions of the ServerThread object in order to send lines etc.
		self.serverthread_object = serverthread_object

	def send(self, line):
		self.serverthread_object.send_line_raw(line)

	def msg(self, recipient, message):
		"""Make sending PRIVMSGs much nicer"""
		line = 'PRIVMSG ' + recipient + ' :' + message
		self.serverthread_object.send_line_raw(line)

	def error(self, message):
		self.serverthread_object.logging_channel.send((constants.logmessage_types.internal, constants.internal_submessage_types.error, message))

class LineParsingError(Exception): None

# parse_line(line) → prefix, command, arguments
# Split the line into its component parts
def parse_line(line):
	def read_byte():
		# Read one byte and advance the index
		nonlocal line, index

		if eol():
			raise LineParsingError

		byte = line[index]
		index += 1

		return byte

	def peek_byte():
		# Look at current byte, don't advance index
		nonlocal line, index
		
		if eol():
			raise LineParsingError

		return line[index]

	def eol():
		# Test if we've reached the end of the line
		nonlocal line, index
		return index >= len(line)

	def skip_space():
		# Skip until we run into a non-space character or eol.
		while not eol() and peek_byte() == ord(' '):
			read_byte()

	def read_until_space():
		nonlocal line, index

		if eol():
			raise LineParsingError

		# Try to find a space
		until = line[index:].find(b' ')

		if until == -1:
			# Space not found, read until end of line
			until = len(line)
		else:
			# Space found, add current index to it to get right index
			until += index

		# Slice line upto the point of next space / end and update index
		data = line[index:until]
		index = until

		return data

	def read_until_end():
		nonlocal line, index

		if eol():
			raise LineParsingError
		
		# Read all of the data, and make index point to eol
		data = line[index:]
		index = len(line)

		return data

	index = 0

	prefix = None
	command = None
	arguments = []

	if peek_byte() == ord(':'):
		read_byte()
		prefix = read_until_space()

	skip_space()

	command = read_until_space()

	skip_space()

	while not eol():
		if peek_byte() == ord(':'):
			read_byte()
			argument = read_until_end()
		else:
			argument = read_until_space()

		arguments.append(argument)

		skip_space()

	return prefix, command, arguments

def handle_line(line, *, irc):
	try:
		prefix, command, arguments = parse_line(line)
	except LineParsingError:
		irc.error("Cannot parse line" + line.decode(encoding = 'utf-8', errors = 'replace'))

	# TODO: handle line