#!/bin/bash

set -e

CURRENT_VERSION=$(cat VERSION)

read -p "Current version is $CURRENT_VERSION. Input new version: " NEW_VERSION

if [ "$CURRENT_VERSION" == "$NEW_VERSION" ]; then
  echo "New version is the same as the old one."
  exit 1
fi

echo "Updating VERSION file. (Press Enter)"
read
echo "$NEW_VERSION" > VERSION

echo "Adding VERSION file and making a version bump commit. (Press Enter)"
read
git add VERSION
git commit -m "version bump $NEW_VERSION"

echo
echo "Making an annotated tag. First line should be '$NEW_VERSION Some-Code-Name' then a new line and change notes. (Press Enter)"
read
git tag -a "$NEW_VERSION"

echo "Pushing changes and new release to github. (Press Enter)"
read
git push
git push origin tag "$NEW_VERSION"
