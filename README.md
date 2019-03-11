# Yakiniku Flask Food Blog

This is a food blog engine created with [Flask](http://flask.pocoo.org/) and [Bulma](http://bulma.io). It is as bare as possible (i.e. no pictures, sorry!) while trying to be very swaggy.

Don't forget to change SECRET_KEY in config.py if you deploy this on your own server.

## Features

* Minimal
* :eggplant:
* Recipe tagging

Local Development
------------------
Set environment variable Yakiniku_DATABASE_URL to point to a valid postgresql database instance, which has the **hstore** extension installed

    export YAKINIKU_DATABASE_URL=postgresql://[username]:[password]@localhost/[yourdatabase]

Then run:

    python app.py

to start a development server.

Browse to http://127.0.0.1:5000/init in order to create the first admin cook with name: admin and pw: password .
Once logged-in you can then change the credentials and create more cooks. Make sure to set the `DEBUG` and `TESTING` option in your config.py to `False` when you take your blog into prodcution.

