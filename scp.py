import threading
import Queue
import getopt
import sys
import os
import paramiko
import getpass
from socket import timeout as SocketTimeout

global buff_size
buff_size = 16384
global recursive
recursive = False
global channelTo, channelFrom
msg = None
ack = None
def ack(channel):
    # read scp response
    recv = ''
    try:
        recv = channel.recv(512)
    except SocketTimeout:
    	print "timeout while waiting for ack"
    	sys.exit(0)
    if recv and recv[0] == '\x00':
        return
    elif recv and recv[0] == '\x01':
    	print "exception\n"
    	print recv[1:]
    	sys.exit(0)
    elif channel.recv_stderr_ready():
        recv = channel.recv_stderr(512)
        print "exception\n"
        print recv
    elif not recv:
    	print "No reponse from the server while waiting for ack\n"
    	sys.exit(0)
    else:
    	print "Invalid response form the server while waiting for ack\n"
    	sys.exit(0)


def read_stats(name):
	stats = os.stat(name)
	mode = oct(stats.st_mode)[-4:]
	size = stats.st_size
	atime = int(stats.st_atime)
	mtime = int(stats.st_mtime)
	return (mode, size, mtime, atime)



def upload_nextDir(channel,directory):
    (mode, size, mtime, atime) = read_stats(directory)
    filename = os.path.basename(directory)
    # if preserve_times:
    #     _send_time(mtime, atime)
    channel.sendall('D%s 0 %s\n' %(mode, filename.replace('\n', '\\^J')))
    ack(channel)

def upload_prevDir(channel):
    channel.sendall('E\n')
    ack(channel)


def changeDir(channel, from_dir, to_dir):
    # Pop until we're one level up from our next push.
    # Push *once* into to_dir.
    # This is dependent on the depth-first traversal from os.walk

    # add path.sep to each when checking the prefix, so we can use
    # path.dirname after
    common = os.path.commonprefix([from_dir + os.path.sep,
                                   to_dir + os.path.sep])
    # now take the dirname, since commonprefix is character based,
    # and we either have a seperator, or a partial name
    common = os.path.dirname(common)
    cur_dir = from_dir.rstrip(os.path.sep)
    while cur_dir != common:
        cur_dir = os.path.split(cur_dir)[0]
        upload_prevDir(channel)
    # now we're in our common base directory, so on
    upload_nextDir(channel, to_dir)


def createSSHChannel(username, host):
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	pbulicKeyFile = os.path.expanduser("~")+'/.ssh/id_rsa.pub'
	try:
		ssh.connect(host, username=username, key_filename=pbulicKeyFile,  look_for_keys=True)
	except:
		print 'public key authentication failed, enter password for '+username+'@'+host
		password = getpass.getpass('Password:')
		try:
			ssh.connect(host, username=username, password=password)
		except paramiko.AuthenticationException:
			print"Authentication failed"
			sys.exit(0)
	global transport

	return ssh


def upload_single_file(channel, dirFrom):
	global buff_size
	filename = os.path.basename(dirFrom)
	fil = open(dirFrom,'rb')
	(mode, size, mtime, atime) = read_stats(dirFrom)
	channel.sendall("C%s %d %s\n" % (mode, size, filename.replace('\n', '\\^J')))
	ack(channel)
	file_pos = 0
	while file_pos < size:
	    channel.sendall(fil.read(buff_size))
	    file_pos = fil.tell()
	channel.sendall('\x00')
	fil.close()
	ack(channel)

def upload(usernameTo, hostTo, dirTo, dirFrom):
	global recursive
	print "uploading file to host"
	#transport = createSSHChannel(usernameTo, hostTo)
	ssh = createSSHChannel(usernameTo, hostTo)
	transport = ssh.get_transport()
	channel = transport.open_session()
	channel.settimeout(5.0)

	# if recursive:
	# 	for root, dirs, fls in os.walk(base)

	dirTo = "'" + dirTo.replace("'", "'\"'\"'") + "'"

	if recursive:
		if not os.path.isdir(dirFrom):
			print dirFrom+"is not a directory"
		else:
			scp_command = "scp -r -t "+dirTo
			channel.exec_command(scp_command)
			ack(channel)
			last_dir = dirFrom
			for root, dirs, files in os.walk(dirFrom):
				changeDir(channel, last_dir, root)
				for f in files:
 					upload_single_file(channel, os.path.join(root, f))
				last_dir = root
	else:
		scp_command = "scp -t "+dirTo
		channel.exec_command(scp_command)
		ack(channel)
		upload_single_file(channel, dirFrom)


def download(usernameFrom, hostFrom, dirFrom, dirTo):
	print "downloadinf file from host"
	ssh = createSSHChannel(usernameFrom, hostFrom)
	transport = ssh.get_transport()
	channel = transport.open_session()
	channel.settimeout(100000.0)
	dirFrom = "'" + dirFrom.replace("'", "'\"'\"'") + "'"
	if recursive:
		scp_command = "scp -r -p -f "+dirFrom
		channel.exec_command(scp_command)
	else:
		scp_command = "scp -p -f "+dirFrom
		channel.exec_command(scp_command)


	while not channel.closed:
		#print "inside while"
		global buff_size
		channel.sendall('\x00')
		msg = channel.recv(1024)
		if not msg: # channel closed while receiving
			print "Success"
			sys.exit(0)
		if(msg[0]=='C'):   #recv_file
			parts = msg[1:].strip().split(' ', 2)
			mode = int(parts[0], 8)
			size = int(parts[1])
			path = os.path.join(dirTo, parts[2])
			fil = file(path, 'wb')
			pos = 0
			channel.send('\x00')
			try:
				while pos < size:
					if size - pos <= buff_size:
						buff_size = size - pos
						fil.write(channel.recv(buff_size))
					pos = fil.tell()
					fil.truncate()
				msg = channel.recv(512)
				if msg and msg[0] != '\x00':
					print "exception\n "+msg[1:]
					sys.exit(0)
			except SocketTimeout:
				channel.close()
				print "exception Socket timeout"
				sys.exit(0)
			fil.truncate()
			os.utime(path, utime)
			utime = None
			os.chmod(path, mode)

			l=len(path)
			print "filename =",str(path)
			for i in range(l,20):  print " ",
			print "size     = "+str(size)+" bytes"
			fil.close()

		elif(msg[0]=='D'):   #next dir
			parts = msg[1:].split()
			try:
				mode = int(parts[0], 8)
				path = os.path.join(dirTo, parts[2])
			except:
				channel.send('\x01')
				print 'Bad directory format'
				sys.exit(0)
			try:
				if not os.path.exists(path):
					print 'no directory exists'
					os.mkdir(path, mode)
				elif os.path.isdir(path):
					os.chmod(path, mode)
				else:
					print path + 'is not a directory'
			except:
				channel.send('\x01no directory')
				print 'no such directory'
				sys.exit(0)
			dirTo = path
		elif(msg[0]=='E'):		#go to prev directory
			dirTo = os.path.split(dirTo)[0]
		elif(msg[0]=='T'):
			times = msg[1:].split()
			mtime = int(times[0])
			atime = int(times[2]) or mtime
			utime = (atime, mtime)

def handle_sshTo(usernameTo, hostTo, dirTo):
	global channelFrom
	sshTo = createSSHChannel(usernameTo, hostTo)
	transportTo = sshTo.get_transport()
	channelTo = transportTo.open_session()
	channelTo.settimeout(5.0)
	dirTo = "'" + dirTo.replace("'", "'\"'\"'") + "'"
	cd_cmd = "cd "+dirTo
	#channelTo.exec_command(cd_cmd)

	if recursive:
		scp_command = cd_cmd+"&& scp -r -t "+dirTo
		channelTo.exec_command(scp_command)
	else:
		scp_command = cd_cmd+"&& scp -t "+dirTo
		channelTo.exec_command(scp_command)


	while not channelFrom.closed:
		ack = channelTo.recv(512)
		while msg == None:
			print "jkdshf"
			pass
		channelTo.sendall(msg)
		if(msg[0] == 'C'):
			msg = None
			ack = channelTo.recv(512)
			pos = 0
			parts = msg[1:].strip().split(' ', 2)
			size = int(parts[1])
			while pos < size:
				if size - pos <= buff_size:
					buff_size = size - pos
				while msg==None:
					pass
				channelTo.sendall(msg)
				pos += len(msg)
				msg = None
			while ack == None:
				pass
			channelTo.sendall(ack)
			ack = None




def handle_sshFrom(usernameFrom, hostFrom, dirFrom):
	sshFrom = createSSHChannel(usernameFrom, hostFrom)
	transportFrom = sshFrom.get_transport()
	channelFrom = transportFrom.open_session()
	channelFrom.settimeout(5.0)
	dirFrom = "'" + dirFrom.replace("'", "'\"'\"'") + "'"
	if recursive:
		scp_command = "scp -r -p -f "+dirFrom
		channelFrom.exec_command(scp_command)
	else:
		scp_command = "scp -p -f "+dirFrom
		channelFrom.exec_command(scp_command)

		while not channelFrom.closed:
		#print "inside while"
			while(ack == None):
				pass
			channelFrom.sendall(ack)
			ack = None
			msg = channelFrom.recv(1024)
			#channelTo.sendall(msg)
		if not msg: # channelFrom closed while receiving
			print "Success"
			sys.exit(0)
		if(msg[0]=='C'):   #recv_file
			parts = msg[1:].strip().split(' ', 2)
			# mode = int(parts[0], 8)
			size = int(parts[1])
			# path = os.path.join(dirTo, parts[2])
			# fil = file(path, 'wb')
			# pos = 0
			while ack == None:
				pass
			channelFrom.send(ack)
			ack = None
			try:
				while pos < size:
					if size - pos <= buff_size:
						buff_size = size - pos
						msg = channelFrom.recv(buff_size)
						#channelTo.sendall(content)
					pos += len(content)
					#fil.truncate()
				ack = channelFrom.recv(512)
				# if msg and msg[0] != '\x00':
				# 	print "exception\n "+msg[1:]
				# 	sys.exit(0)
			except SocketTimeout:
				channelFrom.close()
				print "exception Socket timeout"
				sys.exit(0)


def remoteToremote(usernameTo, hostTo, dirTo, usernameFrom, hostFrom, dirFrom):
	global cha
	print "inside r2r"	
	t1 = threading.Thread(target=handle_sshTo, args=(usernameTo, hostTo, dirTo))
	t1.daemon = True
	t1.start()
	t2 = threading.Thread(target=handle_sshFrom, args=(usernameFrom, hostFrom, dirFrom))
	t2.daemon = True
	t2.start()
	t2.join()
	t1.join()
	#dirFrom = "'" + dirFrom.replace("'", "'\"'\"'") + "'"
	# if recursive:
	# 	scp_command = "scp -r -p -f "+dirFrom
	# 	channelFrom.exec_command(scp_command)
	# else:
	# 	scp_command = "scp -p -f "+dirFrom
	# 	channelFrom.exec_command(scp_command)
	# cd_cmd = "cd "+dirTo
	# channelTo.exec_command(cd_cmd)
	# channelTo.exec_command('pwd')
	# while (not channelTo.recv(buff_size)):
	# 	pass
	
	# while not channelFrom.closed:
	# 	#print "inside while"
	# 	channelFrom.sendall('\x00')
	# 	msg = channelFrom.recv(1024)
	# 	channelTo.sendall(msg)
	# 	if not msg: # channelFrom closed while receiving
	# 		print "Success"
	# 		sys.exit(0)
	# 	if(msg[0]=='C'):   #recv_file
	# 		# parts = msg[1:].strip().split(' ', 2)
	# 		# mode = int(parts[0], 8)
	# 		# size = int(parts[1])
	# 		# path = os.path.join(dirTo, parts[2])
	# 		# fil = file(path, 'wb')
	# 		# pos = 0
	# 		channelFrom.send(channelTo.recv(512))
	# 		try:
	# 			while pos < size:
	# 				if size - pos <= buff_size:
	# 					buff_size = size - pos
	# 					content = channelFrom.recv(buff_size)
	# 					channelTo.sendall(content)
	# 				pos += len(content)
	# 				#fil.truncate()
	# 			channelTo.sendall(channelFrom.recv(512))
	# 			# if msg and msg[0] != '\x00':
	# 			# 	print "exception\n "+msg[1:]
	# 			# 	sys.exit(0)
	# 		except SocketTimeout:
	# 			channelFrom.close()
	# 			print "exception Socket timeout"
	# 			sys.exit(0)
			# fil.truncate()
			# os.utime(path, utime)
			# utime = None
			# os.chmod(path, mode)

			# l=len(path)
			# print "filename =",str(path)
			# for i in range(l,20):  print " ",
			# print "size     = "+str(size)+" bytes"
			# fil.close()

		# elif(msg[0]=='D'):   #next dir
		# 	parts = msg[1:].split()
		# 	try:
		# 		mode = int(parts[0], 8)
		# 		path = os.path.join(dirTo, parts[2])
		# 	except:
		# 		channelFrom.send('\x01')
		# 		print 'Bad directory format'
		# 		sys.exit(0)
		# 	try:
		# 		if not os.path.exists(path):
		# 			print 'no directory exists'
		# 			os.mkdir(path, mode)
		# 		elif os.path.isdir(path):
		# 			os.chmod(path, mode)
		# 		else:
		# 			print path + 'is not a directory'
		# 	except:
		# 		channelFrom.send('\x01no directory')
		# 		print 'no such directory'
		# 		sys.exit(0)
		# 	dirTo = path
		# elif(msg[0]=='E'):		#go to prev directory
		# 	dirTo = os.path.split(dirTo)[0]
		# elif(msg[0]=='T'):
		# 	times = msg[1:].split()
		# 	mtime = int(times[0])
		# 	atime = int(times[2]) or mtime
		# 	utime = (atime, mtime)


def main(argv):
	global recursive
	pathFrom = None
	pathTo = None

	usernameFrom = None
	hostFrom = None
	dirFrom = None

	usernameTo = None
	hostTo = None
	dirTo = None

#parsing the arguments
	if len(argv) < 4:
		print "invalid usage\ntry:\nUsage scp.py [-r recursive] [-f from] <username@host:path/to/file1> [-t to] <to username@host:/path/to/file2>"
		return
	try:
		opts, args = getopt.getopt(argv,"rf:t:",[])
	except getopt.GetoptError:
		print "Correct Use:\nscp.py [-r recursive] [-f from] <username@host:path/to/file1> [-t to] <to username@host:/path/to/file2>"
		return
	for opt, arg in opts:
		if opt == '-f':
			pathFrom = arg
		elif opt == '-t':
			pathTo = arg
		elif opt == '-r':
			recursive = True
			print "detected -r option"
		else:
			print "invalid option %s",opt
			return

#splittimg the from aand to paths because they are of the form username@host:/path/to/file
#We want username, host, path to file seperately
	pathFromSplit = pathFrom.split('@',1)
	if len(pathFromSplit) == 2 :
		usernameFrom = pathFromSplit[0]
		pathFromSplit = pathFromSplit[1].split(':',1)
		if len(pathFromSplit) == 2 :
			hostFrom = pathFromSplit[0]
			dirFrom = pathFromSplit[1]
		else:
			hostFrom = pathFromSplit[0]
	else:
		dirFrom = pathFromSplit[0]	

	pathToSplit = pathTo.split('@',1)
	if len(pathToSplit) == 2 :
		usernameTo = pathToSplit[0]
		pathToSplit = pathToSplit[1].split(':',1)
		if len(pathToSplit) == 2 :
			hostTo = pathToSplit[0]
			dirTo = pathToSplit[1]
		else:
			hostTo = pathToSplit[0]
	else:
		dirTo = pathToSplit[0]	

	if hostFrom == None and hostTo!=None :
		upload(usernameTo, hostTo, dirTo, dirFrom)
	elif hostFrom!=None and hostTo == None :
		download(usernameFrom, hostFrom, dirFrom, dirTo)
	else :
		remoteToremote(usernameTo, hostTo, dirTo, usernameFrom, hostFrom, dirFrom)



if __name__ == "__main__":
	main(sys.argv[1:])
