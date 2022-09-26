Minimimal non-scaleable implementation of the gpodder API.

This provides enough of the API to allow AntennaPod synchronisation.

API documentation can be found at
https://media.readthedocs.org/pdf/gpoddernet/latest/gpoddernet.pdf

Usage
=====

Create a user (only bcrypt password hashing is supported):

$ htpasswd -B -b -c htpasswd jelmer blah

# Run the server

$ python3 -m litegpodder -l 0.0.0.0 -d data --auth htpasswd
