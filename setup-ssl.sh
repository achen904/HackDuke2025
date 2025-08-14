#!/bin/bash

# SSL Certificate Setup Script for Duke Eats
# This ensures SSL certificates exist before nginx starts

SSL_DIR="/opt/duke-eats/ssl"
CERT_FILE="$SSL_DIR/cert.pem"
KEY_FILE="$SSL_DIR/key.pem"

echo "🔒 Setting up SSL certificates..."

# Create SSL directory if it doesn't exist
mkdir -p "$SSL_DIR"

# Check if certificates already exist and are valid
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo "✅ SSL certificates already exist, checking validity..."
    
    # Check if certificate is still valid (not expired)
    if openssl x509 -in "$CERT_FILE" -checkend 86400 -noout; then
        echo "✅ SSL certificates are valid and not expiring soon"
        exit 0
    else
        echo "⚠️  SSL certificates are expired or expiring soon, regenerating..."
    fi
fi

echo "🔧 Generating new SSL certificates..."

# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/C=US/ST=NC/L=Durham/O=Duke University/OU=Duke Eats/CN=dukebdeats.colab.duke.edu/emailAddress=admin@duke.edu" \
    -addext "subjectAltName=DNS:dukebdeats.colab.duke.edu,DNS:localhost,DNS:*.colab.duke.edu,IP:127.0.0.1"

# Set appropriate permissions
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

echo "✅ SSL certificates generated successfully!"
echo "   Certificate: $CERT_FILE"
echo "   Private Key: $KEY_FILE"

# Verify the certificate
echo "📋 Certificate details:"
openssl x509 -in "$CERT_FILE" -text -noout | grep -E "(Subject:|DNS:|IP:|Not After)"
