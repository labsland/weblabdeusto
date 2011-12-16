#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2009 University of Deusto
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

import unittest
import datetime

from weblab.data.experiments import ExperimentId, ExperimentInstanceId, CommandSent, FileSent, ExperimentUsage


class ExperimentIdsTestCase(unittest.TestCase):
    
    def setUp(self):
        self.experiment_id          = ExperimentId('exp', 'cat')
        self.experiment_instance_id = ExperimentInstanceId('inst', 'exp', 'cat')
        # self.command_sent1          = CommandSent('command', ''
        # TODO

    def _check_repr(self, obj):
        self.assertEquals(repr(obj), repr(eval(repr(obj))))

    def test_experiment_id(self):
        self._check_repr(self.experiment_id)
        
    def test_experiment_instance_id(self):
        self._check_repr(self.experiment_instance_id)

def suite():
    return unittest.makeSuite(ExperimentIdsTestCase)

if __name__ == '__main__':
    unittest.main()
