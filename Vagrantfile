# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  # The most common configuration options are documented and commented below.
  # For a complete reference, please see the online documentation at
  # https://docs.vagrantup.com.
  # boxes at https://atlas.hashicorp.com/search.
  config.vm.box = "ubuntu/xenial64"
  config.vm.network "forwarded_port", guest: 6543, host: 6543, host_ip: "127.0.0.1"
  config.vm.synced_folder ".", "/vagrant", disabled: true
  config.vm.synced_folder ".", "/vagrant/spline"

  # Enable provisioning with a shell script. Additional provisioners such as
  # Puppet, Chef, Ansible, Salt, and Docker are also available. Please see the
  # documentation for more information about their specific syntax and use.
  config.vm.provision "shell", privileged: true, inline: <<-ROOT
    chown ubuntu:root /vagrant
    echo "~~ Installing packages"
    apt-get update
    apt-get install -y python3 python3-dev gcc git imagemagick libgit2-24 libgit2-dev libffi-dev libxslt1-dev libxml2-dev postgresql postgresql-client libpq-dev python3-pip
    pip3 install virtualenv --upgrade
    echo "~~ Setting up database"
    adduser splineuser --gecos "" --disabled-password --shell /usr/sbin/nologin
    sudo -u postgres -- psql --command="CREATE USER splineuser WITH PASSWORD 'splinepw';"
    sudo -u postgres createdb -O splineuser splinedb
  ROOT

  config.vm.provision "shell", privileged: false, inline: <<-VAGRANT
    cd /vagrant
    git clone https://github.com/eevee/floraverse_com
    cd /vagrant/spline
    git submodule deinit .
    git submodule init
    git submodule update
    virtualenv . --python=/usr/bin/python3 --always-copy
    source bin/activate
    pip install -e .
    pip install colorama markdown pygit2 psycopg2
    cd /vagrant/floraverse_com
    pip install -e .
  VAGRANT
end
