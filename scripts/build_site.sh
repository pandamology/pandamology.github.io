#!/usr/bin/env bash
# Build and check all public outputs from _data/cv.json.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/prepare_build.py "$@"
cv_updated=$(python3 -c 'import json; print(json.load(open("build/cv-config.yml"))["cv_updated"])')
cv_as_of=$(python3 -c 'import json; print(json.load(open("build/cv-config.yml"))["cv_as_of"])')
python3 scripts/build_cv.py --updated "$cv_updated" --as-of "$cv_as_of" --output build/CV.pdf --tex-output build/CV.tex
bundle exec jekyll build --config _config.yml,build/cv-config.yml --destination _site
mkdir -p _site/files
cp build/CV.pdf _site/files/CV.pdf
python3 scripts/verify_build.py --site _site --pdf _site/files/CV.pdf
