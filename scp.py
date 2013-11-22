import os
import paramiko


hostname = 'csews48.cse.iitk.ac.in'
port = 22
username = 'mohitkg'
password = 'kanp25161cseiit'


# hostkeytype = None
# hostkey = None
# files_copied = 0

# try:
#     host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
#     print "loaded known hosts from ~/.ssh/known_hosts"
# except IOError:
#     try:
#         # try ~/ssh/ too, e.g. on windows
#         host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/ssh/known_hosts'))
#         print "loaded known hosts form ~/ssh/known_hosts"
#     except IOError:
#         print '*** Unable to open host keys file'
#         host_keys = {}

# if host_keys.has_key(hostname):
#     hostkeytype = host_keys[hostname].keys()[0]
#     hostkey = host_keys[hostname][hostkeytype]
#     print 'Using host key of type %s' % hostkeytype
# try:
#     print 'Establishing SSH connection to:', hostname, port, '...'
#     t = paramiko.Transport((hostname, port))
#     t.connect(username=username, password=password, hostkey=hostkey)
#     channel = t.open_session()
#     print channel
#     #stdin, stdout, stderr = channel.exec_command("uptime")
#     #print stdout.readlines()
#     #t.start_client()
# except Exception, e:
#     print '*** Caught exception: %s: %s' % (e.__class__, e)
#     try:
#         t.close()
#     except:
#         pass
def recv_confirm():
    # read scp response
    msg = ''
    try:
        msg = channel.recv(512)
    except SocketTimeout:
    	print "timeout"
    	pass
        #raise SCPException('Timout waiting for scp response')
    if msg and msg[0] == '\x00':
        return
    elif msg and msg[0] == '\x01':
    	print "exception"
    	pass
        #raise SCPException(msg[1:])
    elif channel.recv_stderr_ready():
        msg = channel.recv_stderr(512)
        print "exception"
    	pass
        #raise SCPException(msg)
    elif not msg:
    	print "exception"
    	pass
        #raise SCPException('No response from server')
    else:
    	print "exception"
    	pass
        #raise SCPException('Invalid response from server: ' + msg)


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
def main():
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(
	    paramiko.AutoAddPolicy())
	try:
		ssh.connect(hostname, username=username, 
	    password=password)
	except e:
		print e
	transport = ssh.get_transport()
	channel = transport.open_session()
	channel.settimeout(5.0)
	# channel.exec_command("pwd")
	# msg = channel.recv(512)
	channel.exec_command("scp -t ~/")
	msg = channel.recv(512)
	print msg
	send_files('sent.txt')

#print "sfadfsa"
# stdin, stdout, stderr = ssh.exec_command("uptime")
# type(stdin)
# stdout.readlines()