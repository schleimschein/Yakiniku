import os

class Config(object):
    DEBUG = True
    TESTING = True
    SECRET_KEY = "31t158yuaj2289iusysxd987as8cqjgkl3p97jsbtxsaq"
    DATABASE_URL = os.environ.get("TRUNKS_DATABASE_URL")
