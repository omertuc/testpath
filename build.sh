#!/bin/bash

set -euxo pipefail

python3 code.py
npx @vscode/vsce package
