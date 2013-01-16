#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005 onwards University of Deusto
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
# This software consists of contributions made by many individuals,
# listed below:
#
# Author: Pablo Orduña <pablo@ordunya.com>
#

import os
import re
import json
import time
import urllib2
import datetime
import threading
import traceback

import weblab.experiment.concurrent_experiment as ConcurrentExperiment
import weblab.core.coordinator.coordinator as Coordinator

from voodoo.override import Override

# Core variables
WEBCAMS_INFO             = 'webcams_info'
CONTROLLER_ADDRESS       = 'controller_address'
HISTORIC_DIRECTORY       = 'historic_directory'
LIGHT_BOOTSTRAPPING_TIME = 'light_bootstrapping_time' # How long does the light need to turn on

# Debugging variables
FAKE_CONTROLLER    = 'fake_controller'
VERBOSE_CONTROLLER = 'verbose_controller'
FAKE_NEXT_HOUR     = 'fake_next_hour'

# 
# Controller HTTP interface (deployed in a raspberry):
# 
#     /EGGSOFF -> Turn all the egg lights off
#     /EGGSON  -> Turn all the egg lights on
#     /EGG/1/value/on  -> Turn light of egg #1 off. Range 1..3
#     /EGG/1/value/off -> Turn light of egg #1 off. Range 1..3
# 

class StatusManager(threading.Thread):
    """ StatusManager interacts with the Controller. Duties:
    - Validate and process requests (turn_light)
    - Every fixed time, take a picture of the eggs and store it.
    """
    def __init__(self, cfg_manager, webcams_urls):
        """
        Initialize the StatusManager. webcams_urls is a dictionary such as:
        [ ('1', 'http://.../image.jpg'), ('2', 'http://.../image.jpg') ... ]
        """
        # Initialize thread
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.setName("IncubatorStatusManager")

        # Retrieve configuration
        self._address      = cfg_manager.get_value(CONTROLLER_ADDRESS)
        self._light_time   = cfg_manager.get_value(LIGHT_BOOTSTRAPPING_TIME, 3)
        self._dir          = cfg_manager.get_value(HISTORIC_DIRECTORY, None)

        self._fake           = cfg_manager.get_value(FAKE_CONTROLLER, False)
        self._verbose        = cfg_manager.get_value(VERBOSE_CONTROLLER, False)
        self._fake_next_hour = cfg_manager.get_value(FAKE_NEXT_HOUR, False)

        self._webcams_urls = webcams_urls
        self._lights       = len(webcams_urls)

        # Create a HTTP opener which disables any possible proxy
        # so as to avoid that the request goes to the proxy.
        self._opener  = urllib2.build_opener(urllib2.ProxyHandler({}))

        # 
        # status: initialized to off
        # 
        self._status = {
            # 1 : 'off',
            # 2 : 'off',
            # 3 : 'on',
            # ...
            # 'temp' : 24.3
        }

        self._all_lights = [ light for (light, webcam_url) in self._webcams_urls ]
        for light in self._all_lights:
            self._status[light] = 'off'

        self._file_regex = re.compile('\d\d_\d\d')
    
        # Temperature: initialize with something which does not make sense
        self._status['temp'] = -100.0

        # 
        # Use this lock to acquire status. It must be *fast*
        self._status_lock = threading.Lock()

        # 
        # Use this lock to acquire operations
        self._operations_lock = threading.Lock()

        # 
        # Start with all the lights off
        self.turn_light('all','off')

    def get_status_str(self):
        with self._status_lock:
            return json.dumps(self._status)

    def turn_light(self, number, new_status):
        """
        Turn a particular light (number = '1') or all the lights (number = 'all') on or off.
        If a string is returned, an error has ocurred and the error message may be logged and
        even returned. If None is returned, everything was fine.
        """
        if new_status not in ('on','off'):
            return "Wrong status!"
            
        # Lock the operation, so two threads can not change the status
        with self._operations_lock:
            
            # Lock the status, but make a fast operation
            with self._status_lock:
                if number == 'all':
                    for light in self._all_lights:
                        self._status[number] = new_status
                elif number in self._all_lights:
                    self._status[number] = new_status
                else:
                    return 'Wrong number! (use "all" or 1-%s' % self._lights
            
            if number == 'all':
                return self._perform_request('/EGGS%s' % new_status.upper())
            else:
                return self._perform_request('/EGG/%s/value/%s' % (number, new_status))

    def _perform_request(self, location):
        """
        Encapsulate the communication with the raspberry. Make fakes possible.
        """

        if self._verbose:
            print "%s: Performing request to: %s" % (datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S.%s'), location)
        if self._fake:
            print "Request faked"
            return None

        try:
            url = 'http://%s%s' % (self._address, location)
            response = self._opener.open(url, data = '').read()
            if response != 'ok':
                return 'Invalid response. Expected "ok", got: %s' % response
        except Exception as e:
            traceback.print_exc()
            return 'Error: %s' % e
        else:
            return None

    def _store_picture(self):

        # Create today's directory
        now = datetime.datetime.now()
        year_dir = os.path.join(self._dir, str(now.year))
        if not os.path.exists(year_dir):
            os.mkdir(year_dir)
        month_dir = os.path.join(year_dir, str(now.month))
        if not os.path.exists(month_dir):
            os.mkdir(month_dir)
        day_dir  = os.path.join(month_dir, str(now.day))
        if not os.path.exists(day_dir):
            os.mkdir(day_dir)

        # Populate the directory
        for light, webcam_url in self._webcams_urls:
            try:
                image = self._opener.open(webcam_url).read()
                
                webcam_dir = os.path.join(day_dir, light)
                if not os.path.exists(webcam_dir):
                    os.mkdir(webcam_dir)

                image_file_path = os.path.join(webcam_dir, '%s_%s' % (now.hour, now.minute) )
                open(image_file_path, 'wb').write(image)
            except:
                traceback.print_exc()
                pass

    def retrieve_historic(self, year, month, day):
        """ 
        Retrieve a dictionary such as:
        {
            '1' : [ '00:30', '01:00', '01:30', '02:00' ...],
            '2' : [ '00:30', '01:30', '02:00' ...],
            '3' : [ '00:30', '01:00', '01:30', '02:00' ...],
        }

        Where camera number 2 does not have any measurement at 01:00 (due to a 
        webcam error, or network error, etc.)
        """
        if self._dir is None:
            # No storage: no data
            data = {}
            for light in self._all_lights:
                data[light] = []
            return data

        data = {}
        day_dir = os.path.join(self._dir, str(year), str(month), str(day))
        for light in self._all_lights:
            webcam_dir = os.path.join(day_dir, light)
            current_data = []
            data[webcam_dir] = current_data
            if os.path.exists(webcam_dir) and os.path.isdir(webcam_dir):
                for f in os.listdir(webcam_dir):
                    if os.path.isfile(f) and self._file_regex.match(f):
                        current_data.append(f)
        
        return data

    def _take_historic(self):
        self.turn_light('all', 'on')
        time.sleep(self._light_time)

        self._store_picture()

        self.turn_light('all', 'off')

    def run(self):
        if self._dir is None:
            # If the directory is None, don't take historic data
            return

        while True:
            now = datetime.datetime.now()
            # Sleep until next hour (61: make sure it's passed)
            next_minute = 61 - now.second
            if self._fake_next_hour:
                next_hour = next_minute
            else:
                next_hour = 60 * 59 - now.minute + next_minute
            time.sleep(next_hour)
            self._take_historic()
 

class IncubatorExperiment(ConcurrentExperiment.ConcurrentExperiment):
    """
    Incubator experiment. It's a concurrent experiment, so it supports multiple
    students running the laboratory at the very same time. It relies on the 
    StatusManager class for interacting with the raspberry.
    """
    def __init__(self, coord_address, locator, cfg_manager, *args, **kwargs):
        super(IncubatorExperiment,self).__init__(*args, **kwargs)
        webcams_info    = cfg_manager.get_value(WEBCAMS_INFO, [])

        self.initial_configuration = {}
        webcams_urls = []
        for pos, webcam_config in enumerate(webcams_info):
            num = pos + 1
            webcam_url   = webcam_config.get('webcam_url')
            mjpeg_url    = webcam_config.get('mjpeg_url')
            mjpeg_width  = webcam_config.get('mjpeg_width')
            mjpeg_height = webcam_config.get('mjpeg_height')

            if webcam_url is not None:
                self.initial_configuration['webcam%s' % num] = webcam_url
                webcams_urls.append( (str(num), webcam_url) )
            if mjpeg_url is not None:
                self.initial_configuration['mjpeg%s' % num] = mjpeg_url
            if mjpeg_width is not None:
                self.initial_configuration['mjpegWidth%s' % num] = mjpeg_width
            if mjpeg_height is not None:
                self.initial_configuration['mjpegHeight%s' % num] = mjpeg_height
        self.initial_configuration['webcams'] = len(webcams_info)

        self._status_manager = StatusManager(cfg_manager, webcams_urls)
        self._status_manager.start()


    @Override(ConcurrentExperiment.ConcurrentExperiment)
    def do_get_api(self):
        return "2_concurrent"


    @Override(ConcurrentExperiment.ConcurrentExperiment)
    def do_start_experiment(self, lab_session_id, serialized_client_initial_data, serialized_server_initial_data):
        status_str = self._status_manager.get_status_str()

        config = {
            'status' : json.loads(status_str),
        }

        return json.dumps({ "initial_configuration" : json.dumps(config), "batch" : False })


    @Override(ConcurrentExperiment.ConcurrentExperiment)
    def do_dispose(self, lab_session_id):
        return 'ok'


    @Override(ConcurrentExperiment.ConcurrentExperiment)
    def do_send_command_to_device(self, lab_session_id, command):
        
        # get_status => status
        if command.startswith('get_status'):
            return self._status_manager.get_status_str()

        # turn:1:on => status (or "error:Message"
        if command.startswith('turn:'):
            remainder = command[len('turn:'):]
            regex = re.compile('([^:]*):(on|off)')
            obj = regex.match(remainder)
            if obj is None: 
                return "error:Malformed turn: command"
            number, new_state = obj.groups()
            
            message = self._status_manager.turn_light(number, new_state)

            if message is not None:
                return "error:%s" % message

            return self._status_manager.get_status_str()
    
        # get_historic:2012/12/31 => dictionary with the data
        if command.startswith('get_historic:'):
            remainder = command[len('get_historic:'):]
            regex = re.compile('(\d*)/(\d*)/(\d*)')
            obj = regex.match(remainder)
            if obj is None:
                return "error:Malformed get_historic command"
            year, month, day = obj.groups()
            return self._status_manager.retrieve_historic(year, month, day)

        return 'Command not found'


    @Override(ConcurrentExperiment.ConcurrentExperiment)
    def do_send_file_to_device(self, lab_session_id, content, file_info):
        return 'Not implemented'

