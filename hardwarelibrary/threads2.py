from threading import Thread, Lock
import time

lock = Lock()
counter = 0

def countTogetherInTheBackground(label):
  global lock
  global counter
  for i in range(100):
    lock.acquire()
    counter = counter + 1
    print("{0} is at: {1}".format(label, i))
    lock.release()
    time.sleep(1)

process1 = Thread(target=countTogetherInTheBackground, kwargs=dict(label="Thread1"))
process2 = Thread(target=countTogetherInTheBackground, kwargs=dict(label="Thread2"))

process1.start() 
process2.start() 

