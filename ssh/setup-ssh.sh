#!/bin/bash
mkdir -p /config/.ssh

if [ -f /config/id_rsa.pub ]; then
    cat /config/id_rsa.pub > /config/.ssh/authorized_keys
    echo "SSH Key imported successfully"
fi

chown -R 1000:1000 /config/.ssh
chmod 700 /config/.ssh
chmod 600 /config/.ssh/authorized_keys