import os
import sys

root = os.path.dirname(
    	  os.path.dirname(
        	os.path.dirname(
              os.path.abspath(__file__)
	        )
	      )
        )

# append module root directory to sys.path
sys.path.insert(0, "{0}/hardwarelibrary/communication".format(root))
sys.path.insert(0, "{0}/hardwarelibrary/spectrometers".format(root))
sys.path.insert(0, "{0}/hardwarelibrary/lasersources".format(root))
sys.path.insert(0, "{0}/hardwarelibrary".format(root))
sys.path.insert(0, root)
