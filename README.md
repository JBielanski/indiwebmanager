# INDI Web Manager

INDI Web Manager is a simple Web Application to manage [INDI](http://www.indilib.org) server. It supports multiple driver profiles along with optional custom remote drivers. It can be used to start INDI server locally, and also to connect or **chain** to remote INDI servers.

![INDI Web Manager](https://github.com/JBielanski/indiwebmanager/blob/master/images/indiwebserver.png)

# Installation

INDI Library must be installed on the target system. The Web Application is based on [Bottle Py](http://bottlepy.org) micro-framework. It has a built-in webserver and by default listens on port 8624. Install the pre-requisites:

##UBUNTU

```
$ sudo apt-get -y install gpsd python-requests python-psutil python-bottle python-gps python-dateutil python-tz
```

Next install Pthon Adafruit DHT: [Adafruit_Python_DHT](https://github.com/adafruit/Adafruit_Python_DHT)

Copy the **servermanager** folder to your home directory $(HOME) or any folder where the user has read and write access.

##GENTOO

Run as a ROOT user:

```
$ emerge -av sci-geosciences/gpsd app-misc/dateutils dev-python/python-dateutil dev-python/psutil dev-python/bottle dev-python/requests dev-python/pytz
```

Next install Pthon Adafruit DHT: [Adafruit_Python_DHT](https://github.com/adafruit/Adafruit_Python_DHT)

Copy the **servermanager** folder to /usr/local/lib/ directory and and set appropriate privilages for files: 'read' for all files, 'write' for databases files and 'execution' for scripts.

# Usage

The INDI Web Manager can run as a standalone server. It can be started manually by invoking python:

```
$ cd servermanager
$ python drivermanager.py
```

Then using your favorite web browser, go to http://localhost:8624 if the INDI Web Manager is running locally. If the INDI Web Manager is installed on a remote system, simply replace localhost with the hostname or IP address of the remote system.

# Auto Start

## OPENRC GENTOO

To enable the INDI Web Manager to automatically start after a system reboot, a openrc service file and bash script are provided for your convenience.
My Raspberry PI is configured for providing INDI service by LAN connection (LAN connection has configured as DHCP router with IP 10.0.0.1).
WIFI card is using for INTERNET connection.

``` 
#!/sbin/openrc-run
# /etc/init.d/indiwebserver
#
# INDI webserver startup script
# Service script: need /usr/local/sbin/indiwebserver
#

name=$RC_SVCNAME
command="/usr/local/sbin/indiwebserver"
command_args=""
command_user="root"
start_stop_daemon_args="--args-for-start-stop-daemon"
command_background="yes"

depend() {
        need net.eth0
	need ntp-client
}

start() {
    ebegin "Starting INDI WEBserver"
    start-stop-daemon --background --start --exec \
    		      /usr/local/sbin/indiwebserver start \
		      --pidfile /var/run/indiwebserver.pid
    eend $?
}

stop() {
    ebegin "Stoping INDI WEBserver"
    start-stop-daemon --stop --exec \
		      /usr/local/sbin/indiwebserver stop \
		      --pidfile /var/run/indiwebserver.pid
    eend $?
}

restart() {
    ebegin "Restarting INDI WEBserver"
    start-stop-daemon --restart --exec \
		      /usr/local/sbin/indiwebserver restart \
		      --pidfile /var/run/indiwebserver.pid
    eend $?
}
```

and starting BASH script:

```
#!/bin/sh
# /etc/init.d/indiwebserver
#
# INDI webserver startup script
#

SCRIPT="$0"
LOCKFILE="/var/run/indiwebserver.pid"
IP="10.0.0.1"
PORT="8624"

# Check python exist
if [ ! -x /usr/bin/python2 ]; then
    echo "Python 2.x has not found in system!!! Exit!!!"
    exit -1
fi

# Check tools
if [ ! -f /usr/local/lib/servermanager/drivermanager.py ] || [ ! -f /usr/local/lib/servermanager/autostart.py ]; then
    echo "Server has not existed in /usr/local/lib/servermanager/ directory, please download it first from https://github.com/knro/indiwebmanager !!! Exit!!!"
    exit -1
fi

# -------------------------
# NETWORK INTERFACE
# -------------------------
case "$2" in

	#ETH0
	eth0)
		IP="10.0.0.1"
		echo "Interface eth0 with ip: $IP"
		;;

	#WLAN0
	wlan0)
		IP=`ifconfig wlan0 | grep "inet " | awk -F'[: ]+' '{ print $3 }'`
		echo "Interface wlan0 with ip: $IP"
		;;

	*)
		IP="10.0.0.1"
		echo "Default interface eth0 with ip: $IP"
		;;
esac

# -------------------------
# INDIWEBSERVICE functions:
# -------------------------
case "$1" in

    # Run service
    start)
	PID="0"
	if [ -f ${LOCKFILE} ]; then
	    PID=`cat $LOCKFILE`
	fi
	if [ ${PID} = 0 ]; then
	    echo "-> Starting INDI WEBserver"

	    # Run server as root user
	    /usr/bin/python2 /usr/local/lib/servermanager/drivermanager.py $IP & echo $! > ${LOCKFILE} &

	    echo "-> INDI WEBserver is running..."
	    echo "-> Server address with LAN connection is: http://${IP}:${PORT}"

	else
	    echo "-> INDI WEBserver is running with pid ${PID}..."
	    echo "-> Server address with LAN connection is: http://${IP}:${PORT}"
	fi
	;;

    # Stop service
    stop)
	PID="0"
	if [ -f ${LOCKFILE} ]; then
	    PID=`cat $LOCKFILE`
	fi
	if [ ${PID} != 0 ]; then
	    echo "-> Stop INDI WEBserver"

	    # Kill all astropi uses processes
	    kill -9 ${PID}
	    rm -f ${LOCKFILE}

	    echo "-> INDI WEBserver is stopped"

	else
	    echo "-> INDI WEBserver is already stopped"
	fi
	;;


    # Restart service
    restart)
	$SCRIPT stop && $SCRIPT start "$2"
	;;

    # Status of service
    status)
	PID="0"
	if [ -f ${LOCKFILE} ]; then
	    PID=`cat $LOCKFILE`
	fi

	if [ ${PID} != 0 ]; then
	    echo "-> INDI WEBserver is running with pid ${PID} on ${IP}:${PORT}"
	else
	    echo "INDI WEBserver is NOT running"
	fi
	;;

    *)
	echo "INDI WEBserver"
	echo "Usage: /etc/init.d/indiwebserver {start|stop|restart|status}"
	;;
esac

exit 0
```

To install scripts please call INSTALL bash script from openrc directory:

```
$ cd openrc
$ sudo bash INSTALL
```

## SYSTEMD

To enable the INDI Web Manager to automatically start after a system reboot, a systemd service file is provided for your convenience:

```
[Unit]
Description=INDI Web Manager
After=multi-user.target

[Service]
Type=idle
User=pi
ExecStart=/usr/bin/python /home/pi/servermanager/drivermanager.py
ExecStartPost=/usr/bin/python /home/pi/servermanager/autostart.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

The above service files assumes you copied the servermanager directory to /home/pi, so change it to whereever you installed the directory on your target system. The user is also specified as **pi** and must be changed to your username.

If you selected any profile as **Auto Start** then the INDI server shall be automatically started when the service is executed on start up.

Copy the indiwebmanager.service file to **/lib/systemd/system**:

```
sudo cp indiwebmanager.service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/indiwebmanager.service
```

Now configure systemd to load the service file during boot:

```
sudo systemctl daemon-reload
sudo systemctl enable indiwebmanager.service
```

Finally, reboot the system for your changes to take effect:

```
sudo reboot
```

After startup, check the status of the INDI Web Manager service:

```
sudo systemctl status indiwebmanager.service
```

If all appears OK, you can start using the Web Application using any browser.

# Profiles

The Web Application provides a default profile to run simulator drivers. To use a new profile, add the profile name and then click  the plus button. Next, select which drivers to run under this particular profile. After selecting the drivers, click the **Save** icon to save all your changes. To enable automatic startup of INDI server for a particular profile when the device boots up or when invoked manually via the **systemctl** command, check the **Auto Start** checkbox.

# API

INDI Web Manager provides a RESTful API to control all aspects of the application. Data communication is via JSON messages. All URLs are appended to the hostname:port running the INDI Web Manager.

## INDI Server Methods

### Get Server Status

 URL | Method | Return | Format
--- | --- | --- | ---
/api/server/status | GET | INDI server status (running or not) | {'server': bool}

**Example:** curl http://localhost:8624/api/server/status
**Reply:** [{"status": "False"}]

### Start Server

 TODO

### Stop Server
URL | Method | Return | Format
--- | --- | --- | ---
/api/server/stop | POST | None | []

### Get running drivers list
URL | Method | Return | Format
--- | --- | --- | ---
/api/server/drivers | GET | Returns an array for all the locally running drivers | {'driver': driver_executable}

**Example:** curl http://localhost:8624/api/server/drivers
**Reply:** [{"driver": "indi_simulator_ccd"}, {"driver": "indi_simulator_telescope"}, {"driver": "indi_simulator_focus"}]

## Profiles

### Add new profile
URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles/<name> | POST | None | None

To add a profile named **foo**:

```
curl -H "Content-Type: application/json" -X POST http://localhost:8624/api/profiles/foo
```

### Delete profile
URL | Method | Return | Format
--- | --- | --- | ---
/api/profiles/<name> | DELETE | None | None

To delete a profile named **foo**:

```
curl -X DELETE http://localhost:8624/api/profiles/foo
```

### Get All Profiles

TODO

### TODO

# Author

Jasem Mutlaq (mutlaqja@ikarustech.com)
Jan Bielanski (jbielan@agh.edu.pl)
