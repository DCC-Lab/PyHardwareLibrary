from threading import Thread, RLock

def countInTheBackground(label):
  for i in range(20):
    print("{0} is at: {1}".format(label, i))

process1 = Thread(target=countInTheBackground, kwargs=dict(label="Thread1"))
process2 = Thread(target=countInTheBackground, kwargs=dict(label="Thread2"))

process1.start() 
process2.start() 


lock = RLock()


def countTogetherInTheBackground(label):
  for i in range(20):

    print("{0} is at: {1}".format(label, i))

process1 = Thread(target=countInTheBackground, kwargs=dict(label="Thread1"))
process2 = Thread(target=countInTheBackground, kwargs=dict(label="Thread2"))

process1.start() 
process2.start() 

