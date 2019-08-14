# Introduction

It often occurs that we would like to have an operation performed in the background while we do something else.  For instance, we may want to perform a calculation and update a graph as the calculation gets refined.  We may also want to listen to a serial port while we print other information to the screen.  In this small document, I will show you one way of achieving this:  `threads`.

## Threads

A simple program usually has a single *thread*, that is it goes from start to finish, and if there is a loop, it will complete the loop, then eventually leave the program.  It is the simplest program.  However, all operating systems support *threads*, which allow a single program to run several small tasks in parallel.  These small tasks are called threads.  They can all access the same memory, the same objects. In the simplest case, a thread will perform a computation and let the other thread know when it has completed so that it can display it.

```python
from threading import Thread

def countInTheBackground(label):
  for i in range(20):
    print("{0} is at: {1}".format(label, i))

process1 = Thread(target=countInTheBackground, kwargs=dict(label="Thread1"))
process2 = Thread(target=countInTheBackground, kwargs=dict(label="Thread2"))

process1.start() 
process2.start() 

```



## Threads that communicate

It is not as simple as it looks to have two threads communicate: if two threads attempt to access the same variable and modify it at the same time 1) the program may crash, 2) unexpected behaviour may occurs (overwriting a value).