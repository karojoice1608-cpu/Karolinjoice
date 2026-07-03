#!/bin/bash
set -e

echo "=== Installing lightweight dependencies for cloud deployment ==="
pip install -r requirements-render.txt

echo "=== Pre-downloading NLTK data ==="
python -c "
import nltk
for pkg in ['punkt', 'punkt_tab', 'stopwords', 'wordnet', 'averaged_perceptron_tagger']:
    try:
        nltk.download(pkg, quiet=True)
    except:
        pass
print('NLTK done')
"

echo "=== Build complete! ==="

