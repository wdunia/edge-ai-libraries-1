#!/bin/sh
# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

env | while IFS='=' read -r key value; do
  case "$key" in
    VITE_*|APP_*)
      echo "$key=$value"
      find /opt/share/nginx/html -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' \) -exec sed -i "s|${key}|${value}|g" '{}' +
      ;;
  esac
done
