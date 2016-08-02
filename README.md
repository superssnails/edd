# Experiment Data Depot

The Experiment Data Depot (EDD) is a web-based repository of processed biological data obtained via
experimentation.  See the deployed version at [public-edd.jbei.org][1].
    
## Contents
* [Getting Started](#Getting_Started)
* [For Developers](#For_Developers)
   * [Mac OS Setup](#MacOS_Setup)
       * [XCode](#XCode)
       * [HomeBrew](#HomeBrew)
       * [Docker](#Docker)
       * [Running EDD](#Run_OSX)
   * [Linux / Debian](#Debian)
* [Helpful Python Packages](#Helpful_Python)
* [Build Tools](#BuildTools)
* [Configuring social logins](#Social)

---------------------------------------------------------------------------------------------------

## Getting Started <a name="#Getting_Started"/>

Launching the entire EDD software stack is as simple as cloning the git repository and running:

    ./init-config.sh
    docker-compose up -d

This requires [Docker][2] and [docker-compose][3] are already installed. The launched copy of EDD
will be using default values for all configuration, so some functions (e.g. TLS support, external
authentication) will not work.

There is some minimal configuration of the service startup process exposed via environment
variables. Each item in the following list can be triggered by prepending a value to the command,
e.g.:

    EDD_HOST_DIR=/usr/local/edd/ POSTGRES_DUMP_URL=postgres://edd:edd@pg.example.org:5432/edd \
        docker-compose up -d
        
Remember that these values will persist in the shell and in Docker Compose,
so you should be careful to unset them and `docker-compose down` to avoid
undesirable effects such as accidentally building the database multiple times. At the time of writing,
Docker Compose does not re-read the environment when a single single service
is restarted.

* `EDD_HOST_DIR` changes the location where Docker will look for the EDD code. If not set, Docker
  will issue a warning that the variable will be set to an empty string. If unset or empty, Docker
  will look for EDD code in the current directory, `.`. This is fine for running Docker on a Mac
  with Docker Machine, or running directly on Linux; however, if you are running a Docker client on
  another host, this variable allows you to specify the directory containing code on the Docker
  daemon host. *If set, this value must end with a `/`*.
* `EDD_HOST_TLS` changes the location where Docker will look for certificates to use in securing
  HTTPS traffic to EDD. On first startup, the `nginx` service will generate a self-signed
  certificate for use in HTTPS. If this variable is set, then the `nginx` service will copy
  certificates from the variable location. See the README in `./docker_services/nginx` for more
  information.
* `POSTGRES_DUMP_FILE` points to a database dump file to be loaded into the `postgres` service
  database. This should be a file generated by the `pg_dump` command on an existing EDD database.
  Note that while this variable is defined, *the database will be reloaded each time the `appserver`
  container is started*, so it's best to provide it at the command line as demonstrated above. 
* `POSTGRES_DUMP_URL` points to a database URL to be loaded into the `postgres` service database.
  This variable takes precedence over `POSTGRES_DUMP_FILE`. The URL should be in the format
  `postgres://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE_NAME}`.
  Note that while this variable is defined, *the database will be reloaded each time the `appserver`
  container is started*, so it's best to provide it at the command line as demonstrated above.

---------------------------------------------------------------------------------------------------

## For Developers <a name="For_Developers"/>
The typescript build process includes some comments that will change with every rebuild. These
comments will cause unnecessary merge conflicts if allowed into the repo, so the project includes
some configuration to strip them out.

Upon cloning a repo for the first time (or updating a repo from before filtering), run
`.gitconfig.sh`. If updating an existing repo, you may need to add changed files to the index once.
Some bundled git versions are outdated and cannot use the configuration contained in the script; 
you may need to install a newer version of git; [Homebrew](#HomeBrew) instructions below will
install a more recent version on Macs.
   
### Mac OS Setup <a name="MacOS_Setup"/>
This section contains directions for setting up a development environment on EDD in Mac OS.

* XCode <a name="XCode"/>
    * Install XCode (and associated Developer Tools) via the App Store
    * As of OS X 10.9 "Mavericks": `xcode-select --install` to just get command-line tools
* Homebrew <a name="HomeBrew"/>
    * [Homebrew][4] is a package manager for OS X. The Homebrew packages handle installation and
      dependency management for Terminal software. The Caskroom extension to Homebrew does the
      same for GUI applications.
    * To install:
      `ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"`
      and follow prompts.
    * `brew doctor` should say `Your system is ready to brew.` or describe any problems.
    * From the edd root directory, `brew bundle` should install additional software dependencies.
    * It is a good idea to occaisionally run `brew update` to refresh Homebrew's list of available
      packages and versions; and run `brew upgrade` to install updated versions of your installed
      Homebrew packages.
* Docker <a name="Docker"/>
    * [Docker][2] is a container virtualization platform: all software, configuration, and
      dependencies required to run a service are packaged into standalone images. These images are
      ready to run immediately upon being copied to a new host running a Docker daemon.
    * Docker will be installed already via Homebrew in the previous step.
    * Set up Docker Machine; a tool to manage Docker daemons running on other hosts.
        * Create a VM to run containers:
          `docker-machine create --driver virtualbox default`
        * Confirm VM is running with:
          `docker-machine ls`
        * Stop and start VMs with:
          `docker-machine stop default` and `docker-machine start default`
        * Configure the `docker` command to use the virtualbox VM as the container host:
          `eval "$(docker-machine env default)"`
        * See more in the [Docker Machine documentation][5]
    * Running Docker images
        * Verify Docker is configured by running: `docker run --rm hello-world`
            * Get `docker: command not found`? You didn't successfully install from Homebrew.
            * Get `docker: Cannot connect to the Docker daemon.`? You have not run the `eval`
              command in the Docker Machine section.
    * Try the command `docker-compose`
        * If you get `Illegal instruction: 4`, you have an older Mac that cannot run with the
          compiled binary provided by the Homebrew packages; run `pip install docker-compose` to
          fix the error.
        * Normal output is helptext showing the commands to use with `docker-compose`.
    * Setting up Docker for EDD
        * The default virtualbox settings allocate 1 CPU core and 1 GB RAM for the container host
          VM. This should be fine for small or testing deployments. For better performance, it is
          recommended to increase the allocated resources to at least 2 CPU and 2 GB RAM, by
          stopping the VM and changing settings in the "System" tab of the virtualbox Settings GUI.
        * Create a `./edd/settings/local.py` file, based on the example in
          `./edd/settings/local.py-example`
            * Any local-specific settings changes will go here. The local settings are loaded last,
              and will override any settings contained in other files in the `./edd/settings`
              folder.
        * Create `secrets.env` based on the example in `secrets.env-example`
            * the value of `SECRET_KEY` is the Django server key; pick some random text
            * `secret1` is a password you choose for the `postgres` PostgreSQL user
            * `secret2` is a password you choose for the `edduser` PostgreSQL user
            * `secret3` is a password you choose for the `edd_user` RabbitMQ user
            * `secret4` is a password you choose for the `flower` Flower user
            * the value of `ICE_HMAC_KEY` is the key used to authenticate to ICE; set this to the
              secret used in the ICE instance you connect to for test
            * the value of `LDAP_PASS` is the password for the `jbei_auth` user by default; you may
              use your own password by including in your `./edd/settings/local.py`:
              `AUTH_LDAP_BIND_DN = 'lblEmpNum=[your-six-digit-id],ou=People,dc=lbl,dc=gov'`
* Running EDD <a name="Run_OSX"/>
    * `docker-compose` commands
        * Build all services:  `docker-compose build`
        * Startup all services in detached mode: `docker-compose up -d`
        * View logs: `docker-compose logs`
        * Bringing down all services: `docker-compose down`
        * See more in the [Docker Compose documentation][3]
        * Compose may complain about a missing variables. If this bothers you, run an export
          command to assign an empty string to each: `export EDD_HOST_DIR=`
    * Other useful sample commands:
	      * Connect to the Postgres command line: `docker-compose exec postgres psql -U postgres`
        * Connect to the Django shell: `docker-compose exec appserver python manage.py shell`
    * Startup in new shell sessions
        * The `docker` command will look for a Docker daemon running on the local machine by
          default. Mac hosts currently must use a daemon running in a VirtualBox guest VM. Load
          the Docker environment on the guest with:

              eval "$(docker-machine env default)"

        * Docker will re-use built images, so changes to code may not be reflected in running
          containers. (Re)build the container images with current code using:

              docker-compose build

        * Start EDD services:  `docker-compose up -d`
            * To run commands in __new__ containers, use `docker-compose run $SERVICE $COMMAND`,
              e.g.: `docker-compose run edd python manage.py shell`
            * Run commands in __existing__ containers with `docker-compose exec $SERVICE $COMMAND`,
              e.g.: `docker-compose exec appserver python manage.py shell`
            * To access services, use the IP listed in `docker-machine ip default`, e.g.
                * access EDD via https://192.168.99.100/
                * access Solr via http://192.168.99.100/solr/
                * access RabbitMQ Management Plugin via http://192.168.99.100/rabbitmq
            * Restart misbehaving services with:  `docker-compose restart $SERVICE`
			
### Common Development Tasks

Some of these sample commands will only work as written at JBEI, but should serve as useful examples for common development tasks.
Directions assume that docker containers are already running in the development environment.

* Create an unprivileged test account


    docker-compose exec appserver /code/manage.py shell
	from main.models import User
	user=User.objects.create_user('unprivileged_user', 'test_user@nowhere.com', 'insecure_pwd_ok_for_local_testing')
	^D
	
	# Attempt login using the UI -- this is necessary to enable the following step
	
    # Enable the test account:
	docker-compose exec postgres psql -U postgres edd
	select * from account_emailaddress where email = 'test_user@nowhere.com'; 
	update account_emailaddress set verified = true where email = 'test_user@nowhere.com';
	
* Dump the production database to file and load into a local test deployment:

    Create a dump file:
    pg_dump -h postgres.jbei.org -d eddprod -f edd-prod-dump.sql -U your_username'
    
    Load a dump file:
    docker-compose down
    POSTGRES_DUMP_FILE=edd-prod-dump.sql docker-compose up -d

### Linux / Debian <a name="Debian"/>

* Follow the Docker-recommended instructions for [installing the daemon for your distro][11].
    * There is a `docker` package in the Debian apt repos. It is not [Docker][2].
    * There is a `docker.io` package too; this can work, but it will generally be outdated.
* Create a user for running EDD; assuming user `jbeideploy` exists for further instructions.
* As `jbeideploy`, check out code to `/usr/local/edd/` (this will be `$EDD_HOME` below)
    * Create a `$EDD_HOME/edd/settings/local.py` file, based on the example in
      `$EDD_HOME/edd/settings/local.py-example`
        * Any local-specific settings changes will go here. The local settings are loaded last,
          and will override any settings contained in other files in the `$EDD_HOME/edd/settings`
          folder.
    * Create `secrets.env` based on the example in `$EDD_HOME/secrets.env-example`
        * `SECRET_KEY` is the Django server key; pick some random text
        * `secret1` is a password you choose for the `postgres` PostgreSQL user
        * `secret2` is a password you choose for the `edduser` PostgreSQL user
        * `secret3` is a password you choose for the `edd_user` RabbitMQ user
        * `secret4` is a password you choose for the `flower` Flower user
        * `ICE_HMAC_KEY` is the key used to authenticate to ICE; set this to the secret used
          in the ICE instance you connect to for test
        * `LDAP_PASS` is the password for the `jbei_auth` user by default; you may use your own
          password by including in your `$EDD_HOME/edd/settings/local.py`:
          `AUTH_LDAP_BIND_DN = 'lblEmpNum=[your-six-digit-id],ou=People,dc=lbl,dc=gov'`
* Launching EDD and services
    * _If using docker client on same host_: work from the `$EDD_HOME` directory
    * _If using docker client on a different host, i.e. with docker-machine_
        * Ensure you have a public key in `jbeideploy`'s `~/.ssh/authorized_keys2` file
        * Create an environment for the remote host (replace `{REMOTE_HOST}` with hostname or IP)

              docker-machine create --driver generic \
                  --generic-ip-address {REMOTE_HOST} \
                  --generic-ssh-user jbeideploy \
                  --generic-ssh-key /path/to/private.key \
                  {NAME_OF_ENVIRONMENT}

        * Activate the machine with `eval $(docker-machine env {NAME_OF_ENVIRONMENT})`
        * Set environment variable on docker client host `EDD_HOST_DIR` to `$EDD_HOME`
            * Prepend `EDD_HOST_DIR=/usr/local/edd/` to any `docker-compose` commands
            * Alternatively, `export EDD_HOST_DIR=/usr/local/edd/` before running commands
            * The trailing `/` is important!
    * (Re)build the container images with `docker-compose -f docker-production.yml build`
    * Start EDD services with `docker-compose -f docker-production.yml up -d`

---------------------------------------------------------------------------------------------------

## Helpful Python Packages <a name="Helpful_Python"/>

* django-debug-toolbar `pip install django-debug-toolbar`
    * Include `debug_toolbar` in `./edd/settings/local.py` INSTALLED_APPS

---------------------------------------------------------------------------------------------------

## Build Tools <a name="BuildTools"/>

* The EDD makes use of Node.js and grunt for builds; it would be a good idea to:
    * OS X:
        * Install node; this is already included in the Brewfile
        * Install the grunt command line: `npm install -g grunt-cli`
        * Install node packages to the local folder: `npm install`
    * Debian:
        * `sudo apt-get install node`
        * This will install nodejs.  It might be convenient for you to link this to ‘node’
          on the command line, but there is sometimes already a program
          ’/usr/sbin/ax25-node’ linked to node.
          This is the “Amateur Packet Radio Node program” and is probably not useful to you.
          (https://packages.debian.org/sid/ax25-node)
          Check on this link with `ls -al /usr/sbin/n*` and `rm /usr/sbin/node` if necessary, then
          `sudo ln -s /usr/bin/nodejs /usr/bin/node`
        * `sudo apt-get install npm`
        * `sudo npm install -g grunt-cli`
        * `sudo npm install grunt`

* EDD uses [TypeScript][6] for its client-side interface
    * Dependencies are listed in `packages.json` and may be installed with `npm install`
    * Compile changes in `*.ts` to `*.js` by simply running `grunt` from the edd base directory

---------------------------------------------------------------------------------------------------

## Configuring Social Logins <a name="Social"/>
* For broad overview, refer to the [django-allauth documentation][7].
* To use a new provider:
    * Add the provider application to `INSTALLED_APPS`
    * Put logos in `./main/static/main/images/` and update styles in `./main/static/main/login.css`
    * From the admin site, add a new Social application, using Client ID and Secret Key from
      provider
        * [Github registration][8]
        * [Google registration][9]
        * [LinkedIn registration][10]
        * Each provider may require additional details about the application, allowed domains
          and/or URLs, etc.

## Javascript Tests <a name="Javascript Tests"/>
* run `$ grunt test` to test javascript files.
* cd into main/fixtures/node-server and run `$ nodejs node main.js` In a different terminal tab
 run `$ grunt screenshots` to test
graphs

[1]:    https://public-edd.jbei.org
[2]:    https://docker.io
[3]:    https://docs.docker.com/compose/overview/
[4]:    http://brew.sh
[5]:    https://docs.docker.com/machine/overview/
[6]:    http://typescriptlang.org/
[7]:    http://django-allauth.readthedocs.org/en/latest/index.html
[8]:    https://github.com/settings/applications/new
[9]:    https://console.developers.google.com/
[10]:   https://www.linkedin.com/secure/developer?newapp=
[11]:   https://docs.docker.com/engine/installation/linux/
