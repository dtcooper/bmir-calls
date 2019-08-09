#!/bin/sh

echo 'DROP DATABASE IF EXISTS testing; CREATE DATABASE testing;' | psql -U postgres
