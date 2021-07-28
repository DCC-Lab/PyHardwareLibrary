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
Heavily modified by D. C. Cote 2021
"""

class Notification:
    def __init__(self, name, object=None, userInfo=None):
        self.name = name
        self.object = object
        self.userInfo = userInfo

class ObserverInfo:
    def __init__(self, observer, method=None, notificationName=None, observedObject=None):
        self.observer = observer
        self.method = method
        self.observedObject = observedObject
        self.notificationName = notificationName

    def matches(self, otherObserver) -> bool:
        if self.notificationName is not None and otherObserver.notificationName is not None and self.notificationName != otherObserver.notificationName:
            return False
        elif self.observedObject is not None and otherObserver.observedObject is not None and self.observedObject != otherObserver.observedObject:
            return False
        elif self.observer != otherObserver.observer:
            return False
        return True

    # def __eq__(self, rhs):
    #     return self.matches(rhs)

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
        observerInfo = ObserverInfo(observer=observer, method=method, notificationName=notificationName, observedObject=observedObject)

        if notificationName not in self.observers.keys():
            self.observers[notificationName] = []

        if observerInfo not in self.observers.values():
            self.observers[notificationName].append(observerInfo)

    def removeObserver(self, observer, notificationName=None, observedObject=None):
        observerToRemove = ObserverInfo(observer=observer, notificationName=notificationName, observedObject=observedObject)

        if notificationName is not None:
            self.observers[notificationName] = [currentObserver for currentObserver in self.observers[notificationName] if not currentObserver.matches(observerToRemove) ]
        else:
            for name in self.observers.keys():
                self.observers[name] = [observer for observer in self.observers[name] if not observer.matches(observerToRemove) ]        

    def postNotification(self, notificationName, notifyingObject, userInfo=None):
        if notificationName in self.observers.keys():
            notification = Notification(notificationName, notifyingObject, userInfo)
            for observerInfo in self.observers[notificationName]:
                if observerInfo.observedObject is None or observerInfo.observedObject == notifyingObject:
                    observerInfo.method(notification)

    def observersCount(self):
        count = 0
        for name in self.observers.keys():
            count += len(self.observers[name])
        return count

    def clear(self):
        self.observers = {}
