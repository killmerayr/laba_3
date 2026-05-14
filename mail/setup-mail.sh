#!/bin/bash

SSL_DIR="/tmp/docker-mailserver/ssl"
mkdir -p "$SSL_DIR"

if [ ! -f "$SSL_DIR/cert.pem" ]; then
    echo "Generating self-signed SSL certificates..."
    openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 \
        -subj "/C=RU/ST=State/L=City/O=Organization/CN=mail.example.local" \
        -keyout "$SSL_DIR/key.pem" \
        -out "$SSL_DIR/cert.pem"
    chmod 600 "$SSL_DIR/key.pem"
fi

setup email add user@example.local pass