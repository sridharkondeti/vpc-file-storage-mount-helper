# Copyright (c) IBM Corp. 2023. All Rights Reserved.
# Project name: VPC File Storage Mount Helper
# This project is licensed under the MIT License, see LICENSE file in the root directory.

#!/bin/bash

user_host="$1"

if [[ "$user_host" == "" ]]; then
    echo "Must provide remote user:host"
    exit -1
fi

dir_test="/tmp/mount_helper/test"
dir_src="/tmp/mount_helper/src"

ssh $user_host "mkdir -p $dir_test && mkdir -p $dir_src"

scp ../src/*.*  "$user_host:$dir_src"
scp ../test/*.* "$user_host:$dir_test"

ssh $user_host "cd $dir_test && ./run_test.sh"

