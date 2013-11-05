# config.py
# Contact: Jacob Schreiber
#			jmschrei@soe.ucsc.edu
#
# This config file stores the customizable data for a particular lab.
# Please enter all configurable information, and other python programs
# will read this file to configure themselves.

# Allows you to view and interact with different databases through the window.
# Currently only supports MySQL databases.

DATABASE_TYPE = "MySQL"					# Type of the database
DATABASE_HOST = "db-01.soe.ucsc.edu"    # If hosted, where the host is
DATABASE_PASSWORD = "OM0gFZzFzPmc+AuZ"  # Password to the database 
DATABASE_USER = "chenoo"                # If required, the username
DATABASE = "chenoo"                     # The name of the database
DATABASE_SOURCE = "NanoporeMetadata"    # Where filenames are stored
MAX_DATABASE_SIZE = 10000               # Maximum number of rows in the database (overshoot this)