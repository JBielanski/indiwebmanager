#!/usr/bin/python

from bottle import Bottle, run, template, static_file, request
from servermanager import startServer, stopServer, isServerRunning, getRunningDrivers
from parsedrivers import driversList, findDriverByLabel, DeviceDriver
from Adafruit_DHT import read_retry
from datetime import datetime
from dateutil import tz
from gps import *
from time import *
import time
import threading
import db
import json
import os
import sys
import socket

# Validate IP
def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False

    return True

# Default IP
my_ip = '10.0.0.1'

# Get IP
if len(sys.argv) == 2:
	if is_valid_ipv4_address(sys.argv[1]):
		my_ip = str(sys.argv[1])
print "IP value for selected network is ", my_ip

dirname, filename = os.path.split(os.path.abspath(__file__))
os.chdir(dirname)

app = Bottle()

saved_profile = None


# Server static files
@app.route('/static/<path:path>')
def callback(path):
    return static_file(path, root="./views")


# Favicon
@app.route('/favicon.ico', method='GET')
def get_favicon():
    return static_file('favicon.ico', root='./')


# Main Page
@app.route('/')
def form():
    global saved_profile
    families = get_driver_families()
    allDrivers = {}
    for family in families:
        drivers = [ob.label for ob in driversList if ob.family == family]
        allDrivers[family] = drivers

    # port = request.get_cookie("indiserver_port")
    # print ("cooke port is " + port)
    # if not port:
    #    port = 7624;

    if not saved_profile:
        saved_profile = request.get_cookie("indiserver_profile")
        if not saved_profile:
            saved_profile = "Simulators"

    allProfiles = get_profiles()
    return template('form.tpl', allProfiles=allProfiles, allDrivers=allDrivers, saved_profile=saved_profile)

''' Profile Operations '''


# Get all profiles
def get_profiles():
    return db.get_profiles()


# Add new profile
@app.post('/api/profiles/<name>')
def add_profile(name):
    db.add_profile(name)


# Get one profile info
def get_profile(name):
    return db.get_profile(name)


# Delete Profile
@app.delete('/api/profiles/<name>')
def delete_profile(name):
    db.delete_profile(name)


# Update profile info (port & autostart)
@app.put('/api/profiles/<name>')
def update_profile(name):
    from bottle import response
    response.set_cookie("indiserver_profile", name,
                        None, max_age=3600000, path='/')
    data = request.json
    db.update_profile(name, data)


# Add drivers to existing profile
@app.post('/api/profiles/<name>/drivers')
def save_profile_drivers(name):
    data = request.json
    db.save_profile_drivers(name, data)

''' Server Options '''


# Server status
@app.get('/api/server/status')
def get_server_status():
    status = [{'status': str(isServerRunning())}]
    json_string = json.dumps(status)
    return json_string


# Server Driver
@app.get('/api/server/drivers')
def get_server_drivers():
    status = []
    for driver in getRunningDrivers():
        status.append({'driver': driver})
    json_string = json.dumps(status)
    return json_string


# Start autostart profile if any
@app.post('/api/server/autostart')
def autostart_server():
    profiles = get_profiles()
    for profile in profiles:
        if profile['autostart'] == 1:
            start_server(profile['name'])
            break


# Start INDI Server for a specific profile
@app.post('/api/server/start/<profile>')
def start_server(profile):
    global saved_profile
    from bottle import response
    alldrivers = []
    saved_profile = profile
    response.set_cookie("indiserver_profile", profile,
                        None, max_age=3600000, path='/')
    info = db.get_profile(profile)
    port = info['port']
    drivers = db.get_profile_drivers_labels(profile)
    for driver in drivers:
        oneDriver = findDriverByLabel(driver['label'])
        alldrivers.append(oneDriver)
        # Find if we have any custom drivers
    custom_drivers = db.get_profile_custom_drivers(profile)
    if (custom_drivers):
        custom_drivers = custom_drivers['drivers'].split(',')
        for driver in custom_drivers:
            newDriver = DeviceDriver(driver, driver, "1.0", driver, "Custom")
            alldrivers.append(newDriver)

    # print ("calling start server internal function")
    if alldrivers:
        startServer(port, alldrivers)


# Stop INDI Server
@app.post('/api/server/stop')
def stop_server():
    global saved_profile
    stopServer()
    # If there is saved_profile already let's try to reset it
    if saved_profile:
        saved_profile = request.get_cookie("indiserver_profile")
        if not saved_profile:
            saved_profile = "Simulators"


''' Driver Operations '''


# Get all drivers
def get_drivers():
    drivers = [ob.__dict__ for ob in driversList]
    return drivers


# Get all drivers families (groups)
def get_driver_families():
    families = [ob.family for ob in driversList]
    families = sorted(list(set(families)))
    return families

''' JSON REQUESTS '''


# Get all driver families (JSON)
@app.get('/api/drivers/groups')
def get_json_groups():
    from bottle import response
    families = [ob.family for ob in driversList]
    families = sorted(list(set(families)))
    json_string = json.dumps(families)
    response.content_type = 'application/json'
    return json_string


# Get all drivers (JSON)
@app.get('/api/drivers')
def get_json_drivers():
    from bottle import response
    json_string = json.dumps([ob.__dict__ for ob in driversList])
    response.content_type = 'application/json'
    return json_string


# Get one profile info
@app.get('/api/profiles/<item>')
def get_json_profile(item):
    results = db.get_profile(item)
    json_string = json.dumps(results)
    return json_string


# Get all profiles (JSON)
@app.get('/api/profiles')
def get_json_profiles():
    results = db.get_profiles()
    json_string = json.dumps(results)
    return json_string


# Get driver labels of specific profile
@app.get('/api/profiles/<item>/labels')
def get_json_profile_labels(item):
    results = db.get_profile_drivers_labels(item)
    json_string = json.dumps(results)
    return json_string


# Get custom drivers of specific profile
@app.get('/api/profiles/<item>/custom')
def get_custom_drivers(item):
    results = db.get_profile_custom_drivers(item)
    json_string = json.dumps(results)
    if (json_string == "null"):
        return []
    else:
        return json_string

# ---------- Extra RaspberryPI 3 Functions -----------

#
# Added support for Adafruit AM2302 Temeperature/Humidity sensor
# Sensor is connected to GPIO 25 ; PIN 22
# Program use Adafruit_DHT driver from https://github.com/adafruit/Adafruit_Python_DHT
#

# AM2302 - 22 / DHT22 - 22 / DHT11 - 11
dht_sensor = 22
# GPIO25 ; PIN 22
dht_pin = '25'

# Get temperature
@app.get('/api/sensors/temperature')
def get_temperature():
	humidity, temperature = read_retry(dht_sensor, dht_pin)
	json_string = json.dumps(float('%.3f' % (temperature)))
	if (json_string == "null"):
        	return []
    	else:
		return json_string

# Get humidity
@app.get('/api/sensors/humidity')
def get_humidity():
       	humidity, temperature = read_retry(dht_sensor, dht_pin)
       	json_string = json.dumps(float('%.3f' % (humidity)))
        if (json_string == "null"):
                return []
        else:
                return json_string

# Get Temperature and Humidity
@app.get('/api/sensors/am2302')
def get_am2302():
	humidity, temperature = read_retry(dht_sensor, dht_pin)
	json_string = json.dumps([float('%.3f' % (temperature)), float('%.3f' % (humidity))])
	if (json_string == "null"):
                return []
        else:
             	return json_string

# ----------- GPS -------------

gpsd = None #seting the global variable

# GPS class
class GpsPoller(threading.Thread):
  def __init__(self):
    threading.Thread.__init__(self)
    global gpsd #bring it in scope
    gpsd = gps(mode=WATCH_ENABLE) #starting the stream of info
    self.current_value = None
    self.running = True #setting the thread running to true

  def run(self):
    global gpsd
    while gpsp.running:
	gpsd.next() #this will continue to loop and grab EACH set of gpsd info to clear the buffer

# Start GPS
gpsp = GpsPoller() # create the thread
gpsp.start() # start it up

# Get latitude
@app.get('/api/sensors/gps/latitude')
def get_gps_latitiude():

	#Test flag
	flag = 0

	#Convert latitude
	latitude = 0.0
	lat_sym = 'N'

	# Repeat getting GPS while they are incorrect
        max_count = 100 # Max waiting in iterations
       	count = 0 # Iteration counter
	while flag==0:
		latitude = gpsd.fix.latitude
		flag = 1
		if math.isnan(latitude):
			flag = 0 # Set flag to 0
                        count = count + 1 # Update couter
                        time.sleep(0.010) # Wait one 10 miliseconds
                        print('Can not get GPS data, attemt: ' + repr(count) + '\n')
                        if count==max_count:
                               	flag = 1 # Set flag to 1 when achived max iteration

	if math.isnan(latitude):
		latitude = '-'
		lat_sym  = ' '
	else:
		if latitude < 0:
			latitude = math.fabs(latitude)
			lat_sym = 'E'

	json_string = json.dumps([latitude, lat_sym])
        if (json_string == "null"):
                return []
        else:
                return json_string

# Get longitude
@app.get('/api/sensors/gps/longitude')
def get_gps_longitude():

	#Test flag
	flag = 0

	#Convert longitude
	longitude = 0.0
	lon_sym = 'E'

	# Repeat getting GPS while they are incorrect
       	max_count = 100 # Max waiting in iterations
        count = 0 # Iteration counter
	while flag==0:
		longitude = gpsd.fix.longitude
		flag = 1
		if math.isnan(longitude):
			flag = 0 # Set flag to 0
                        count = count + 1 # Update couter
                        time.sleep(0.010) # Wait one 10 miliseconds
                        print('Can not get GPS data, attemt: ' + repr(count) + '\n')
                        if count==max_count:
                               	flag = 1 # Set flag to 1 when achived max iteration

	if math.isnan(longitude):
		longitude = '-'
		lon_sym = ' '
	else:
		if longitude < 0:
			longitude = math.fabs(longitude)
			lon_sym = 'W'

       	json_string = json.dumps([longitude, lon_sym])
        if (json_string == "null"):
                return []
        else:
             	return json_string

# Get altitude
@app.get('/api/sensors/gps/altitude')
def get_gps_altitude():

	#Test flag
	flag = 0

	# Conver altitude
	altitude = 0.0
	alt_sym = 'm'

	# Repeat getting GPS while they are incorrect
	max_count = 100 # Max waiting in iterations
	count = 0 # Iteration counter
	while flag==0:
		altitude = gpsd.fix.altitude
		flag = 1
		if math.isnan(altitude):
			flag = 0 # Set flag to 0
			count = count + 1 # Update couter
			time.sleep(0.010) # Wait one 10 miliseconds
			print('Can not get GPS data, attemt: ' + repr(count) + '\n')
			if count==max_count:
				flag = 1 # Set flag to 1 when achived max iteration

	if math.isnan(altitude):
		altitude = '-'
		alt_sym = ' '

        json_string = json.dumps([altitude, alt_sym])
        if (json_string == "null"):
                return []
        else:
             	return json_string


# Get UTC time
@app.get('/api/sensors/gps/utctime')
def get_gps_utctime():

	# Get time from GPS
        utc_time = datetime.strptime(gpsd.utc, "%Y-%m-%dT%H:%M:%S.%fZ")

       	# Timezone from system
        from_zone = tz.tzutc()

	# Give timezone
        utc_time = utc_time.replace(tzinfo=from_zone)

	# Save date/time and zone info
	cur_date = utc_time.strftime('%d/%m/%Y')
        cur_time = utc_time.strftime('%H:%M:%S')
	cur_zone = utc_time.strftime('%Z')

	#Write data to JSON
	json_string = json.dumps([cur_date, cur_time, cur_zone])
        if (json_string == "null"):
                return []
        else:
             	return json_string

# Get LOCAL time
@app.get('/api/sensors/gps/localtime')
def get_gps_localtime():

	# Get time from GPS
        utc_time = datetime.strptime(gpsd.utc, "%Y-%m-%dT%H:%M:%S.%fZ")

        # Timezone from system
        from_zone = tz.tzutc()
	to_zone = tz.tzlocal()

        # Give timezone
        utc_time = utc_time.replace(tzinfo=from_zone)

	# Convert time zone
        local_time = utc_time.astimezone(to_zone)

       	# Save date/time and zone info
        cur_date = local_time.strftime('%d/%m/%Y')
        cur_time = local_time.strftime('%H:%M:%S')
        cur_zone = local_time.strftime('%Z')

	# Write data to JSON
        json_string = json.dumps([cur_date, cur_time, cur_zone])
        if (json_string == "null"):
                return []
        else:
             	return json_string


# Get NEO-6M GPS DATA
@app.get('/api/sensors/gps/gps')
def get_gps_neo6mgps():

	# Test flag
	flag = 0

	# Convert LONGITUDE / LATITUDE / ALTITUDE
	latitude = 0.0
	lat_deg = 0
	lat_min = 0
	lat_sec = 0.0
	lat_sym = 'N'

	longitude = 0.0
	lon_deg = 0
	lon_min = 0
	lon_sec = 0.0
	lon_sym = 'E'
	altitude = 0.0
	alt_sym = 'm'

	# Repeat getting GPS while they are incorrect
	max_count = 100 # Max waiting in iterations
	count = 0 # Iteration counter
	while flag==0:
		latitude = gpsd.fix.latitude
		longitude = gpsd.fix.longitude
		altitude = gpsd.fix.altitude
		flag = 1

		# Wait NaN received
		if math.isnan(latitude) or math.isnan(longitude) or math.isnan(altitude):
			flag = 0 # Set flag to 0
			count = count + 1 # Update couter
			time.sleep(0.010) # Wait one 10 miliseconds
			print('Can not get GPS data, attemt: ' + repr(count) + '\n')
			if count==max_count:
				flag = 1 # Set flag to 1 when achived max iteration


	# Set info and convert coordinates to format deegres / minutes / seconds
	if math.isnan(latitude):
		latitude = '-'
		lat_sym = ' '
	else:
		if latitude < 0.0:
			lat_sym = 'S'
			latitude = math.fabs(latitude)

		lat_deg = int(latitude)
		lat_sec = ((latitude-lat_deg)*10000.0)*0.36
		lat_min = int(lat_sec/60.0)
		lat_sec = lat_sec-(60*lat_min)

		# Rounding results
		latitude = round(latitude,6)
		lat_sec = round(lat_sec,2)

	if math.isnan(longitude):
		longitude = '-'
		lon_sym = ' '
	else:
		if longitude < 0.0:
			lon_sym = 'W'
			longitude = math.fabs(longitude)

		lon_deg = int(longitude)
		lon_sec = ((longitude-lon_deg)*10000)*0.36
		lon_min = int(lon_sec/60.0)
		lon_sec = lon_sec-(60*lon_min)

		# Rounding results
		longitude = round(longitude,6)
		lon_sec = round(lon_sec,2)

	if math.isnan(altitude):
		altitude = '-'
		alt_sym = ' '
	else:
		# Rounding result
		altitude = round(altitude,4)
        	alt_sym = 'm'

	# Covert DATE

	# Get time from GPS
	utc_time = datetime.strptime(gpsd.utc, "%Y-%m-%dT%H:%M:%S.%fZ")

	# Timezone from system
	from_zone = tz.tzutc()
	to_zone = tz.tzlocal()

	# Give timezone
	utc_time = utc_time.replace(tzinfo=from_zone)

	# Convert time zone
	local_time = utc_time.astimezone(to_zone)

	# Rewrite UTC time
	utc_cur_date = utc_time.strftime('%d/%m/%Y')
	utc_cur_time = utc_time.strftime('%H:%M:%S')
	utc_cur_zone = utc_time.strftime('%Z')

	# Rewrite LOCAL time
	local_cur_date = local_time.strftime('%d/%m/%Y')
        local_cur_time = local_time.strftime('%H:%M:%S')
       	local_cur_zone = local_time.strftime('%Z')

	# Write data to JSON
	json_string = json.dumps([latitude, lat_deg, lat_min, lat_sec, lat_sym, longitude, lon_deg, lon_min, lon_sec, lon_sym, altitude, alt_sym, utc_cur_date, utc_cur_time, utc_cur_zone, local_cur_date, local_cur_time, local_cur_zone])
	if (json_string == "null"):
                return []
        else:
             	return json_string

# ------------ INDIWEBSERVER ------------------

# run(app, host='0.0.0.0', port=8080, debug=True, reloader=True)
run(app, host=str(my_ip), port=8624, debug=True)
#run(app, host='10.0.0.1', port=8624, debug=True)

# ----------- EXIT GPS -------------
gpsp.running = False
gpsp.join()

