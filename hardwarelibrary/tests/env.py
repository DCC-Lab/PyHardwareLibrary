import sys
import os

root = os.path.dirname(
    	  os.path.dirname(
        	os.path.dirname(
              os.path.abspath(__file__)
	        )
	      )
        )

# append module root directory to sys.path
sys.path.insert(0, root)
