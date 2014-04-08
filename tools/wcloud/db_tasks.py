import unittest
import celery
import sqlalchemy
from sqlalchemy.sql import text


def connect(user, passwd):
    """
    Connects to the MySQL database using the specified username and password.
    Assumes the DB is in localhost and listening on port 3306.

    @param user: Username, which will need to be root to create new databases.
    @param passwd: Password for the Username.
    """
    conn_string = 'mysql://%s:%s@%s:%d' % (user, passwd, '127.0.0.1', 3306)
    engine = sqlalchemy.create_engine(conn_string)
    engine.execute("SELECT 1")
    return engine


@celery.task
def create_db(root_username, root_password, base_name, db_username, db_password):
    """
    Task to create a MySQL database upon request, which will be used by a WCLOUD instance.

    Assumes: An user has already been created to grant priviledges to.

    @param root_username: MySQL root username, or a username for an account with db creation priviledges.
    @param root_password: MySQL root password.
    @param base_name: Base name to give to the new database. If it exists, a unique name will be created,
    normally by appending a number.
    @param db_username: Username to grant access to.
    @param db_password: Password of the username given access to. This is used only for testing.

    @return: Name of the database that has just been created.
    """

    # Connect to MySQL.
    engine = connect(root_username, root_password)

    # Find a suitable name:
    # Get a list of all current databases.
    dbs = engine.execute(text("SHOW databases LIKE :bn"), bn="%s%%" % base_name)
    dbs = dbs.fetchall()
    dbs = [db[0] for db in dbs]
    # Find the first non-existing name which satisfies the criteria.
    db_name = None
    for i in range(1, 10000):
        db_name = "%s%d" % (base_name, i)
        if db_name not in dbs:
            break

    if db_name is None:
        raise Exception("No suitable db_name found")

    # Create the database.
    engine.execute("CREATE DATABASE %s DEFAULT CHARACTER SET utf8" % db_name)
    engine.execute("GRANT ALL PRIVILEGES ON %s.* TO %s@localhost" % (db_name, db_username))

    # Test that the database was created successfully.
    engine = connect(db_username, db_password)
    engine.execute("USE %s" % db_name)
    engine.execute("SHOW tables").fetchall()

    # If no exception was thrown it was done right.

    return db_name


@celery.task
def destroy_db(root_username, root_password, db_name):
    """
    Destroys the specified database.

    @param root_username: MySQL root username to use.
    @param root_password: MySQL root password to use.
    @param db_name: Name of the database to destroy.
    """
    engine = connect(root_username, root_password)
    engine.execute("DROP DATABASE %s" % db_name)

    return True


######################################
#
# UNIT TESTS BELOW
#
######################################

from nose.tools import assert_is_not_none


class TestDatabaseTasks(unittest.TestCase):

    def test_connect(self):
        """
        Test that we can connect to the database.
        """
        engine = connect("root", "password")
        assert_is_not_none(engine, "Engine is None")

    def test_create_db(self):
        """
        Test that we can successfully create a database.
        """
        db = create_db("root", "password", "wcloudtest", "weblab", "weblab")
        assert db.startswith("wcloudtest")

    def test_destroy_db(self):
        db = create_db("root", "password", "wcloudtest", "weblab", "weblab")
        destroy_db("root", "password", db)
        engine = connect("root", "password")
        dbs = engine.execute("SHOW databases LIKE '%s'" % db).fetchall()
        assert len(dbs) == 0

    def _clearTestDatabases(self):
        engine = connect("root", "password")
        dbs = engine.execute(text("SHOW databases LIKE :bn"), bn="%s%%" % "wcloudtest")
        dbs = dbs.fetchall()
        dbs = [db[0] for db in dbs]
        for db in dbs:
            engine.execute("DROP DATABASE %s" % db)

    def setUp(self):
        self._clearTestDatabases()

    def tearDown(self):
        self._clearTestDatabases()

