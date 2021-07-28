# Copyright (c) 2010, Luca Antiga, Orobix Srl.
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
# 
#     * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
# 
#     * Redistributions in binary form must reproduce the above
#        copyright notice, this list of conditions and the following
#        disclaimer in the documentation and/or other materials provided
#        with the distribution.
# 
#     * Neither the name of Orobix Srl nor the names of any
#        contributors may be used to endorse or promote products derived
#        from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Python implementation of Cocoa NSNotificationCenter
Modified by D. C. Cote 2021
"""
from typing import NamedTuple

class Notification:
    def __init__(self, name, object=None, userInfo=None):
        self.name = name
        self.object = object
        self.userInfo = userInfo

class ObserverInfo(NamedTuple):
    observer:object = None
    method:object = None
    observedObject:object = None

class NotificationCenter:
    _instance = None
    def __init__(self):
        if not hasattr(self, 'observers'):
            self.observers = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance

    def addObserver(self, observer, method, notificationName, observedObject=None):
        observerInfo = ObserverInfo(observer, method, observedObject)

        if notificationName not in self.observers:
            self.observers[notificationName] = []

        if observerInfo not in self.observers.values():
            self.observers[notificationName].append(observerInfo)

    def removeObserver(self, observer, notificationName=None, observedObject=None):
        if notificationName not in self.observers.keys():
            return

        savedObservers = []
        for observerInfo in self.observers[notificationName]:
            if observerInfo.observer != observer or observerInfo.observedObject != observedObject:
                savedObservers.append(observerInfo)
        self.observers = savedObservers

    def postNotification(self, notificationName, notifyingObject, userInfo=None):
        if notificationName in self.observers.keys():
            notification = Notification(notificationName, notifyingObject, userInfo)
            for observerInfo in self.observers[notificationName]:
                if observerInfo.observedObject is None or observerInfo.observedObject == notifyingObject:
                    observerInfo.method(notification)
