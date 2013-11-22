import getopt
import sys
import os
import paramiko
import getpass


buff_size = 16384
global recursive
recursive = False

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

def send_files(file):
	basename = os.path.basename(file)
	(mode, size, mtime, atime) = read_stats(file)
	# if preserve_times:
	#     _send_time(mtime, atime)
	file_hdl = open(file, 'rb')

	# The protocol can't handle \n in the filename.
	# Quote them as the control sequence \^J for now,
	# which is how openssh handles it.
	channel.sendall("C%s %d %s\n" %
	                     (mode, size, basename.replace('\n', '\\^J')))
	recv_confirm()
	file_pos = 0
	# if _progress:
	#     _progress(basename, size, 0)
	buff_size = 16384
	chan = channel
	while file_pos < size:
	    chan.sendall(file_hdl.read(buff_size))
	    file_pos = file_hdl.tell()
	    # if _progress:
	    #     _progress(basename, size, file_pos)
	chan.sendall('\x00')
	file_hdl.close()
	recv_confirm()


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
	except paramiko.AuthenticationException:
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

	# try:
	# 	ssh.connect("webhome.cc.iitk.ac.in", username='agrawals',key_filename=pbulicKeyFile,  look_for_keys=True)
	# except paramiko.AuthenticationException:
	# 	print 'public key authentication failed, enter password'
	# 	pswd = getpass.getpass('Password:')
	# 	try:
	# 		ssh.connect("webhome.cc.iitk.ac.in", username='agrawals', password=pswd)
	# 	except paramiko.AuthenticationException:
	# 		print"Authentication failed"
	# 		return

	# transport = ssh.get_transport()
	# channel = transport.open_session()
	# channel.settimeout(5.0)


	# channel.exec_command("pwd")
	# msg = channel.recv(512)


	# channel.exec_command("scp -t ~/")
	# msg = channel.recv(512)
	# print msa
	# send_files('sent.txt')


if __name__ == "__main__":
	main(sys.argv[1:])

#print "sfadfsa"
# stdin, stdout, stderr = ssh.exec_command("uptime")
# type(stdin)
# stdout.readlines()