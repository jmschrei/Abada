# config.py
# Contact: Jacob Schreiber
#			jmschrei@soe.ucsc.edu
#
# This config file stores the customizable data for a particular lab.
# Please enter all configurable information, and other python programs
# will read this file to configure themselves.

# Allows you to view and interact with different databases through the window.
# Currently only supports MySQL databases.

DATABASE_TYPE = ""					# Type of the database
DATABASE_HOST = ""    				# If hosted, where the host is
DATABASE_PASSWORD = ""  			# Password to the database 
DATABASE_USER = ""                	# If required, the username
DATABASE = ""                     	# The name of the database
DATABASE_SOURCE = ""    			# Where filenames are stored
MAX_DATABASE_SIZE = 10000           # Maximum number of rows in the database (overshoot this)