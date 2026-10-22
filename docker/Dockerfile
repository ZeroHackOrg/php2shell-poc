# Use the exact vulnerable PHP version
FROM php:8.4.26-apache

# Update and install required dependencies
RUN apt-get update && apt-get install -y \
    libzip-dev \
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install zip gd \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy our custom PHP configuration to enable the vulnerable feature
COPY php.ini /usr/local/etc/php/conf.d/99-php2shell-lab.ini

# Copy the custom Apache configuration for a single-worker setup
COPY apache.conf /etc/apache2/conf-available/php2shell-lab.conf

# Enable our custom Apache config and required modules
RUN a2enconf php2shell-lab && a2enmod rewrite

# Create a simple vulnerable target endpoint
# Note: This endpoint intentionally does not call session_start() itself
RUN echo "<?php echo 'ZeroHack php2shell Lab - Target Active'; ?>" > /var/www/html/index.php

# Set proper permissions for the web root
RUN chown -R www-data:www-data /var/www/html

# Expose port 80
EXPOSE 80
