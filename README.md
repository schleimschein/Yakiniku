# Trunks Flask Blog

This is a blog engine created with [Flask](http://flask.pocoo.org/) and [Bulma](http://bulma.io). It is as bare as possible while trying to be very swaggy.

Don't forget to change SECRET_KEY in config.py if you deploy this on your own server.

## Features

* Minimal
* :metal
* Post tagging

Local Development
------------------
Set environment variable TRUNKS_DATABASE_URL to point to a valid postgresql database instance, which has the **hstore** extension installed

    export TRUNKS_DATABASE_URL=postgresql://[username]:[password]@localhost/[yourdatabase]

Then run:

    python app.py

to start a development server.

Browse to http://127.0.0.1:5000/init in order to create the first admin user with username: admin and pw: password .
Once logged-in you can then change the credentials and create more users. Make sure to comment the according method in app.py when you take your blog to production!

