# Experiment Data Depot

 * The Experiment Data Depot (EDD) is a web-based repository of processed data
    obtained via experimentation.
 * [edd.jbei.org](https://edd.jbei.org).

## System Pre-requisites
### MacOS X
 * Install XCode (and associated Developer Tools) via the App Store
    * As of OS X 10.9 "Mavericks": `xcode-select --install` to just get command-line tools
    * Establish `/usr/include` with: ``sudo ln -s `xcrun --show-sdk-path`/usr/include /usr/include``

 * [Homebrew](http://brew.sh)
    * `ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"`
    * `brew doctor`

 * Replace default OS X version of Python with the more up-to-date Homebrew version
    * `brew install python`
    * May need to reload shell to see the proper Python version

 * Replace default OS X version of OpenSSL
    * `brew install OpenSSL`

 * [pip](https://pip.pypa.io)
    * Should be installed as part of Homebrew install of Python
    * For latest version: `sudo pip install --upgrade --no-use-wheel pip`
    * Also a good idea to: `sudo pip install --upgrade setuptools`
    * Manually install by downloading get-pip.py, run `sudo python get-pip.py`

 * PostgreSQL (required for installing psycopg2 driver)
    * `brew install postgresql`
    * Following PostgreSQL steps are optional if using external database server
    * Instructions on startup can be found with `brew info postgresql`
        * Manually start with `postgres -D /usr/local/var/postgres`
    * Enable the hstore extension on all new databases:
        * `psql -d template1 -c 'create extension hstore;'`
    * `createdb edd`
    * `psql edd` and

            CREATE USER edduser WITH PASSWORD 'somegoodpassword'
                NOSUPERUSER INHERIT CREATEDB NOCREATEROLE NOREPLICATION;

 * Tomcat/Solr (optional if using external server for Solr)
    * Install a JDK7+ from [Oracle](http://java.oracle.com)
    * `brew install tomcat solr`
    * Link to easily access tomcat and solr install directories:

            ln -s /usr/local/Cellar/tomcat/(VERSION)/libexec/ /usr/local/tomcat
            ln -s /usr/local/Cellar/solr/(VERSION)/ /usr/local/solr

    * Copy Solr libraries to Tomcat lib:
      `cp /usr/local/solr/example/lib/ext/* /usr/local/tomcat/lib/`
    * Create Solr directories:
      `mkdir -p /usr/local/var/solr`
    * Copy Solr configuration from `edd-django/solr` to `/usr/local/var/solr`
    * `cp /usr/local/solr/libexec/dist/solr-(VERSION).war /usr/local/tomcat/webapps/solr.war`
    * Add a `setenv.sh` to `/usr/local/tomcat/bin/` and `chmod +x /usr/local/tomcat/bin/setenv.sh`
    
            #!/bin/bash
            JAVA_OPTS="$JAVA_OPTS -Dsolr.solr.home=/usr/local/var/solr"

    * Modify `/usr/local/tomcat/conf/server.xml` to only listen on localhost
        * find `<Connector port="8080" ...`
        * add attribute `address="localhost"`
    * Service is controlled with `catalina` command; `catalina start` and `catalina stop`
    * Access admin interface via <http://localhost:8080/solr>

 * Install python packages (these can be combined into one `sudo pip install`)
    * [Arrow](http://crsmithdev.com/arrow/)
        * "Arrow is a Python library that offers a sensible, human-friendly approach to creating,
          manipulating, formatting and converting dates, times, and timestamps."
        * `sudo pip install arrow`
    * [cryptography](https://cryptography.io/en/latest/)
        * Adds some crypto libraries to help play nice with TLS certificates
        * Needs additional env flags to ensure using Brew-installed OpenSSL
        * `env ARCHFLAGS="-arch x86_64" LDFLAGS="-L/usr/local/opt/openssl/lib"
            CFLAGS="-I/usr/local/opt/openssl/include" pip install cryptography`
            * May need to include `--upgrade --force-reinstall` flags after `install` in prior command
    * [Django](https://www.djangoproject.com/)
        * MVC web framework used to develop EDD.
        * `sudo pip install Django`
    * [django-auth-ldap](https://pythonhosted.org/django-auth-ldap/index.html)
        * A Django application providing authentication with an LDAP backend.
        * `sudo pip install django-auth-ldap`
    * [django-extensions](https://django-extensions.readthedocs.org/en/latest/)
        * Adds additional management extensions to the Django management script.
        * `sudo pip install django-extensions`
    * [django-hstore](https://github.com/djangonauts/django-hstore)
        * Supports the PostgreSQL HStore extension for key-value store columns.
        * `sudo pip install django-hstore`
        * Ensure that the hstore extension is enabled on the PostgreSQL template1 database before
          use; details in django-hstore documentation, and command provided in PostgreSQL setup
          above.
        * Requires running `python manage.py collectstatic` to copy static files in all apps to a
          common location; this may need to be run every deploy.
    * [django-registration](http://django-registration-redux.readthedocs.org/en/latest/index.html)
        * A Django application allowing for local-account registration and creation.
        * `sudo pip install django-registration-redux`
    * [requests](http://docs.python-requests.org/en/latest/)
        * "Requests is an Apache2 Licensed HTTP library, written in Python, for human beings."
        * `sudo pip install requests[security]`
    * [psycopg2](http://initd.org/psycopg/)
        * Database driver/adapter for PostgreSQL in Python.
        * `sudo pip install psycopg2`
    * [python-ldap](http://www.python-ldap.org/)
        * Object-oriented client API for accessing LDAP directories.
        * `sudo pip install python-ldap`

 * Use `server.cfg-example` as a template to create a `server.cfg` file
    * Need to put in appropriate values for `site.secret`, `db.pass`, and `ldap.pass`
    * Update `site`, `db`, `solr`, `ldap`, and `ice` for appropriate connection parameters
    * _*DO NOT CHECK THIS FILE INTO SOURCE CONTROL*_

 * Configure LDAP SSL handling in `/etc/openldap/ldap.conf`
    * For OS X 10.9.x "Mavericks":
        * Pull CA certificates from `identity.lbl.gov`
            * As root in `/System/Library/OpenSSL/certs`
                * `openssl s_client -showcerts -connect identity.lbl.gov:636 > godaddy.crt`
                * Edit `godaddy.crt` to remove all non-certificate blocks (outside BEGIN/END), and the
                  first certificate block (the identity.lbl.gov certificate).
        * Edit as root `/etc/openldap/ldap.conf`
            * Add line `TLS_CACERTDIR   /System/Library/OpenSSL/certs`
            * Add line `TLS_CACERT      /System/Library/OpenSSL/certs/godaddy.crt`
        * Test with:

                ldapsearch -H ldaps://identity.lbl.gov -b "ou=People,dc=lbl,dc=gov" -W \
                    -D "uid=jbei_auth,cn=operational,cn=other" -s base "objectclass=*"

    * For OS X 10.10.x "Yosemite":
        * TBD; something changed in certificate checking with ldapsearch
        * Work-around, comment out the `TLS_REQCERT` line

 * The EDD should now be ready to run with an empty database. See Database Conversion below for
   instructions on copying data.
    * From project root, `./manage.py migrate` will create the needed database tables.
    * `./manage.py runserver` will launch the application at <http://localhost:8000/>
    * `./manage.py test main` will run unit tests on the main application
        * Solr tests make use of a different core, see Solr section below.

### Debian
 * `sudo apt-get install -t testing libpq-dev` for headers required by psycopg2

 * `sudo apt-get install libldap2-dev libsasl2-dev libssl-dev` for headers
    required by python-ldap

 * Configure LDAP SSL handling in `/etc/ldap/ldap.conf`
    * Add line `TLS_CACERTDIR   /etc/ssl/certs`
    * Add line `TLS_CACERT  /etc/ssl/certs/ca-certificates.crt`

 * \(_optional_\) `sudo apt-get install tomcat7` for Tomcat/Solr
    * Download [Solr](http://lucene.apache.org/solr/) and copy WAR to webapps folder

 * TODO complete Debian instructions
 
## Helpful Python Packages
 * django-debug-toolbar `pip install django-debug-toolbar`
    * Include `debug_toolbar` in settings.py INSTALLED_APPS

## Build Tools
 * This project makes use of Node.js and grunt for builds; it would be a good
    idea to:
    * `brew install node`
    * `sudo npm install -g grunt-cli`
    * `sudo npm install grunt`

 * EDD uses [TypeScript](http://typescriptlang.org) for its client-side
    interface; you will want:
    * `sudo npm install -g typescript`
    * `sudo npm install grunt-typescript`

 * Compile changes in `*.ts` to `*.js` by simply running `grunt` 

## Database conversion
 1. `pg_dump -i -h postgres.jbei.org -U edduser -F p -b -v -f edddb.sql edddb`
 2. Create a new schema in the django database, e.g. `CREATE SCHEMA edd_old`
 3. Edit the SQL file to prepend the new schema to the `SET search_path` line,
    and replace all instances of `public.` with `edd_old.` (or whatever the
    schema name is)
 4. `psql edd < edddb.sql`
 5. `psql edd < convert.sql`

## Solr
 * Tests in this project make use of a `test` core, which will need to be created
    * Create a new data directory (e.g. `/usr/local/var/solr/data/test`)
    * Add new line to `solr.xml` using same studies `instanceDir` and new data directory

