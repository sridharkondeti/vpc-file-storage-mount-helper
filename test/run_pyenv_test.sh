# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

#!/bin/bash

versions=( "3.4" "3.5" "3.6" "3.7" "3.8" "3.9" "3.10" "3.11")
#versions=("3.4" "3.6") # still being tested

command_exist () {
  type -p "$1"
  if [ 0 -eq $? ]; then
      return 0 #true
  fi;
  return 1 #false
}

activate_pyenv () {
  export PYENV_ROOT="$HOME/.pyenv"
  if [ ! -d "$PYENV_ROOT" ]; then
    echo "pyenv not installed"
    return 1 #false
  fi
  command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init -)"
  if ! command_exist "pyenv"; then
    return 1
  fi
}

check_result () {
  if [ $? -ne 0 ]; then
    echo "$1"
    exit -1
  fi;
}

version_less_than() { 
    ans="$(printf '%s\n%s\n' "$1" "$2" | sort -t '.' -k 1,1 -k 2,2 -k 3,3 -k 4,4 -g | head -n 1)"
    if [ "$ans" == "$2" ]; then
        return 1
    fi;
    return 0
}

pyenv_install () {
  version="$1"
  if version_less_than $version "3.5"; then
    install_older_libssl
  fi;
  echo "pyenv - Installing python $version"
  pyenv install "$version" 
  check_result "Problem installing python: $version"
}

install_older_libssl () {
  PKG="libssl1.0-dev"
  apt list --installed | grep -i "$PKG"
  if [ $? -eq 0 ]; then
    echo "Already installed: $PKG"
    return
  fi;
  SRC_LIST="/etc/apt/sources.list"
  cp "$SRC_LIST" "$SRC_LIST".old
  echo "deb http://security.ubuntu.com/ubuntu bionic-security main" >> "$SRC_LIST"
  apt update && apt-cache policy "$PKG" 
  apt-get install "$PKG" -y
  check_result "Problem installing: $PKG"
  cp "$SRC_LIST".old "$SRC_LIST"
}

install_python () {
  version="$1"
  installed="$(pyenv versions --bare | grep $version.)"
  if [ "$installed" != "" ]; then
    echo "Already installed ($installed)"
    return 
  fi;

  if version_less_than $version "3.5"; then
    install_older_libssl
  fi;
  echo "pyenv - Installing python $version"
  pyenv install "$version" 
  check_result "Problem installing python: $version"
}

get_current_python_version () {
  echo "$(python3 --version 2>&1 | awk '{print $2}')"
}

if ! activate_pyenv; then
  curl https://pyenv.run | bash
  if ! activate_pyenv; then
    echo "problem installing pyenv"
    exit -1
  fi
fi

echo "Check installed python versions"
for version in "${versions[@]}";  do
  install_python "$version"
done;

for version in "${versions[@]}";  do
  echo "Activating $version"
  eval "$(pyenv global $version)"
  CUR_PYTHON_VER="$(get_current_python_version)"
  if [[ "$CUR_PYTHON_VER" != "$version"* ]]; then
    echo "Python not activated Want($version) Have($CUR_PYTHON_VER)"
    exit -1
  fi;
  ./run_test.sh
  check_result "Problem running test: $version"
done


