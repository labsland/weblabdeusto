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

import weblab.login.database.DatabaseGateway as DbGateway
import weblab.database.DatabaseSession as DbSession
import weblab.exceptions.database.DatabaseExceptions as DbExceptions

class LoginDatabaseManager(object):
    
    def __init__(self, cfg_manager):
        self._auth_gateway = DbGateway.create_auth_gateway(cfg_manager)

    def check_credentials(self,username,password):
        try:
            role, user_id, user_auths = self._auth_gateway.check_user_password( username, password )
        except DbExceptions.DbInvalidUserOrPasswordException,e:
            return DbSession.InvalidDatabaseSessionId()

        if user_auths is None:
            return DbSession.ValidDatabaseSessionId( username, role.name )
        else:
            return DbSession.NotAuthenticatedSessionId( username, role.name, user_auths )

