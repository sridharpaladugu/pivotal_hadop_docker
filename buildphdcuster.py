import paramiko 
import sys, subprocess
from subprocess import Popen,PIPE
from os.path import expanduser
import urllib
import time

userhome = expanduser('~')
basepath = userhome + "/git/workspace/"
phdbinariespath = basepath + "/phdbinaries/"
ips = {}
nodesize = 10
user = "root"
passwd = "cyborg"

def greeting():
    msg = "Building pivotal hadoop cluster with "+ str(nodesize) + " nodes."
    msg += "____________________________________________"
    msg += "\nCluster Topology:\n"
    msg += "\nphd0 -> pcc client"
    msg += "\nphd1 -> namenode 1+ Zookeeper 1 + Journal node 1 + hive server"
    msg += "\nphd2 -> namenode 2 + Zookeeper 2 + Journal node 2"
    msg += "\nphd3 -> Resource manager + History Server + Journal node 3 + zookeeper 3"
    msg += "\nphd4 -> HAWQ Master"
    msg += "\nphd5 -> HBase Master"
    msg += "\nphd6 -> Datanode 1 + hawq segment 1"
    msg += "\nphd7 -> Datanode 2 + hawq segment 2"
    msg += "\nphd8 -> Datanode 3 + hawq segment 3"
    msg += "\nphd9 -> Datanode 4 + hawq segment 4"
    msg += "\nphd10 -> Datanode 5 + hawq segment 5"
    msg += "\nphd11 -> phd client"
    msg += "____________________________________________"
    print msg

def runSSHCommand(server,cmd):
    print "Running command : " + cmd + " on server : "+server + " as user : "+user
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(server, username=user, password=passwd)
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
    print ssh_stdout.channel.recv_exit_status()

def createDNSImage():
   cmd = "docker build -t pivotal/phddns " + basepath + "dns/"
   print "Building Docker image pivotal/phddns..."
   print cmd 
   subprocess.call(cmd, shell=True, stderr=subprocess.STDOUT)
   print "Successfully created image!"
      
def createPhdImages():
  for num in range(0, nodesize):
    imagename = "pivotal/phd" + str(num)
    cmd = "docker build -t " + imagename + " " + basepath + "phdbase/"
    print "building docker image "+ imagename + "....."
    print cmd
    subprocess.call(cmd, shell=True, stderr=subprocess.STDOUT)
    print "Successfully created image " + imagename

def launchContainer(imagename, dnsserver, containername, hostname):
    print "Launching container "+imagename
    cmdprefix = "docker run -d --privileged --dns "
    cmdsuffix = " --dns 8.8.8.8 --dns 8.8.4.4 --dns-search pivotal.dev -p 22 -p 80 " 
    cmd = cmdprefix + dnsserver + cmdsuffix
    cmd = cmd + " --name " + containername + " -h " + hostname + " " + imagename   
    print cmd
    subprocess.call(cmd, shell=True, stderr=subprocess.STDOUT)
    print "Done."

def checkcontainerready(server):
    maxtries = 10
    counter = 1
    statuscode = 404
    while(statuscode != 200):
      try:
         print "try number: " + str(counter)
         url = urllib.urlopen("http://" + server + ":80")
         statuscode = url.getcode()
         print statuscode
      except IOError as err:
          if (counter == maxtries):
	     print(err)
             return
          counter += 1
          time.sleep(10)
          continue
    print server + " is completely up!"
  
def launchContainers():
    launchContainer("pivotal/phddns", "127.0.0.1", "phddns", "dns.pivotal.dev")
    cmdprefix = "docker inspect --format \'{{ .NetworkSettings.IPAddress }}\' "
    process = Popen(cmdprefix + "phddns", stdout=PIPE, shell=True)
    dnsip = process.communicate()[0].rstrip()
    ips['dns.pivotal.dev'] = dnsip 
    for num in range(0, nodesize):
       imagename = "pivotal/phd" + str(num) 
       containername = "phd" + str(num)
       hostname = "phd"+str(num)+".pivotal.dev"
       launchContainer(imagename, dnsip, containername, hostname)
       process = Popen(cmdprefix + containername, stdout=PIPE, shell=True)
       ip = process.communicate()[0].rstrip()
       ips[hostname] = ip
    #wait for dns to come up completely.
    checkcontainerready(dnsip)

def setupDNS():
   dnshosts = ''
   for key, value in ips.items():
       line = value + " " + key + " " + key.split(".")[0]
       dnshosts += line +"\n"
   print "*************** DNS entries ******************"
   print dnshosts
   print "**********************************************"
   fdnshosts = open("dnshosts", "w")
   fdnshosts.write(dnshosts)
   fdnshosts.close()
   srcfile = basepath + "dnshosts"
   destfile = "/etc/dnsmasq/dnshosts"
   dnsserver = ips['dns.pivotal.dev']
   copyfile(ips['dns.pivotal.dev'], srcfile, destfile)
   cmd = "kill -9 `ps -aux | grep dnsmasq | awk 'NR==1 {print $2}'`"
   runSSHCommand(dnsserver, cmd)
   cmd = "/usr/sbin/dnsmasq -s pivotal.dev --addn-hosts /etc/dnsmasq/dnshosts -D"
   runSSHCommand(dnsserver, cmd)

def copyfile(server, srcfile, destfile):
   ssh = paramiko.SSHClient()
   ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   ssh.connect(server, username=user, password=passwd)
   print "ssh is successfull."
   ftp = ssh.open_sftp()
   ftp.put(srcfile,destfile)
   ftp.close()

def uploadPHDbinaries():
   cmd = "mkdir /root/phd"
   server = ips['phd0.pivotal.dev']
   runSSHCommand(server, cmd)
   cmd = "mkdir /root/phdbinaries" 
   runSSHCommand(server, cmd) 
   src = phdbinariespath + "PCC-2.3.0-438.x86_64.tar.gz" 
   dest = "/root/phd/PCC-2.3.0-438.x86_64.tar.gz" 
   print "FTP: "+ src +" TO "+dest
   copyfile(ips['phd0.pivotal.dev'], src, dest) 
   src = phdbinariespath + "PHD-2.1.0.0-175.tar.gz" 
   dest = "/root/phdbinaries/PHD-2.1.0.0-175.tar.gz" 
   print "FTP: "+ src +" TO "+dest
   copyfile(ips['phd0.pivotal.dev'], src, dest) 
   src = phdbinariespath + "PADS-1.2.1.0-10335.tar.gz"
   dest = "/root/phdbinaries/PADS-1.2.1.0-10335.tar.gz"
   copyfile(ips['phd0.pivotal.dev'], src, dest) 
   src = phdbinariespath + "PRTS-1.3.0-48613.tar.gz"
   dest = "/root/phdbinaries/PRTS-1.3.0-48613.tar.gz"
   copyfile(ips['phd0.pivotal.dev'], src, dest) 
   src = phdbinariespath + "madlib_1.6-1.2.0.1.tgz"
   dest = "/root/phdbinaries/madlib_1.6-1.2.0.1.tgz"
   copyfile(ips['phd0.pivotal.dev'], src, dest) 

def installPCC():
   cmd = "tar --no-same-owner -zxvf /root/phd/PCC-2.3.0-438.x86_64.tar.gz -C /root/phd"
   server = ips['phd0.pivotal.dev'] 
   runSSHCommand(server, cmd)
   cmd = "cd /root/phd/PCC-2.3.0-438.x86_64;  ./install"
   runSSHCommand(server, cmd)

def main():
    ips['phd0.pivotal.dev'] = '172.17.0.3' 
#   greeting()
#   createDNSImage()
#   createPhdImages()
#   launchContainers()
#   setupDNS()
#   uploadPHDbinaries() 
    installPCC()

if __name__ == '__main__':
    main()
