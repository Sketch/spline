# spline

spline is an attempt to realize a vague daydream: make it easy to build chunks of websites that play together nicely.  Want a blog, a forum, a wiki?  Install those components, and they'll all share the same theme and users and admin UI.

As a secondary goal, it should be easy to spin up a trivial new website, without worrying about the boring repetitive stuff, but without being as opinionated as something like Rails.

🚨🚨🚨 **FAIR WARNING:** 🚨🚨🚨 spline is not finished.  It may never be finished.  It runs in production well enough (powering [Floraverse][]), but its development is currently driven by immediate practical needs.  There is no documentation, and anything may change or break at any time.  Help is appreciated if you get what I'm going for, but you're on your own.


## Getting the goods

**NOTE:** There's a submodule!  You _must_ run `git submodule update --init` after cloning, or intermittently after pulling.  If your CSS seems to be broken, that's why.

### Prerequisites

Use apt or your favorite package installer to get these:

```python3 python3-dev gcc git imagemagick libgit2-24 libgit2-dev libffi-dev libxslt1-dev libxml2-dev postgresql postgresql-client libpq-dev python3-pip```

Other versions of libgit2-24 (such as libgit2-23) will work. On Debian, do not install libgit2-21: pygit2 will fail to install if you do.  The following guide assumes Python 3.4.

On Ubuntu, there is an extra step:
```
sudo pip3 install virtualenv --upgrade
```

Make a virtual environment and activate it:
```virtualenv-3.4 splineweb -p /usr/bin/python3.4```
(if you are in Vagrant's mounted folder on a non linux host: ```virtualenv-3.4 splineweb -p /usr/bin/python3.4 --always-copy```)
```
cd splineweb
source bin/activate
```

### Spline

```git clone https://github.com/eevee/spline --recursive-submodules```

### Floraverse

We'll start with a skin so you have something to look at
```git clone https://github.com/eevee/floraverse_com```

## Prep the DB

First we'll create a new user
```sudo adduser splineuser --shell /usr/sbin/nologin ```
Set his password (I'll use 'splinepw' for this example)

Next, we'll create a corresponding role in postgre (use "splinepw" when prompted for the new role)
```
sudo su - postgres
createuser splineuser -P
createdb -O splineuser splinedb
```

## Installing

Now ```exit``` to come back to your virtual environment
```
cd spline
pip install -e .
pip install colorama markdown pygit2 psycopg2
cd ../floraverse_com
pip install -e .
cd ../spline
```

### Initializing the db

We're almost ready. We need to create the database and populate it. You may want to change some parameters before running it, check them with
```
python -m spline -h
```
We'll go with the defaults here
```
python -m spline --db postgresql+psycopg2://splineuser:splinepw@localhost/splinedb -P spline_comic:comic -P spline_wiki:wiki -P floraverse_com:floraverse_com init-db
```

Then you can create a new user. Add them to the admin group.
````
python -m spline --db postgresql+psycopg2://splineuser:splinepw@localhost/splinedb create-user
````
## Run, Forr-- Spline, run !

Woo.
Now, start the server with
```
python -m spline --db postgresql+psycopg2://splineuser:splinepw@localhost/splinedb -P spline_comic:comic -P spline_wiki:wiki -P floraverse_com:floraverse_com run --data-dir data 0.0.0.0:6543
```

### Adding an image

Open your browser and connect to http://localhost:6543 (or http://the_VM_IP:6543). you should get a message telling you something didn't work, which is normal at this point since you don't have any comic up, so go on and add one. First login at http://localhost:6543/@@auth/login (user = admin, password = test if you kept the default values) then go to http://localhost:6543/comic/@@admin
You should be able to choose an image from your computer, check "publish now" and fill a title and text then submit. Now it should appear in the archive and on the front page.

### Making our first wiki edit

You may have noticed that the "About" and "Contact" pages are blank. Let's fix that. Click on About, and then on create it. You'll have a big text field for you to write in, and a small text field at the bottom to write the edit reason in wiki fashion. In the main field, write down the following:
```markdown
Title: About

This site was made possible thanks to Spline, developed by Eevee and available on [Github](https://github.com/eevee/spline).
```
In the reason box, write ```Initial version```.

Submit. Tada !


[Pyramid]: http://pyramid.readthedocs.org/en/latest/
[Floraverse]: http://floraverse.com/
