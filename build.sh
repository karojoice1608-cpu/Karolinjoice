#!/bin/bash
set -e

echo "=== Installing CPU-only PyTorch first (smaller & faster) ==="
pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cpu

echo "=== Installing remaining dependencies ==="
pip install -r requirements.txt

echo "=== Pre-downloading NLTK data ==="
python -c "
import nltk
for pkg in ['punkt', 'punkt_tab', 'stopwords', 'wordnet', 'averaged_perceptron_tagger']:
    nltk.download(pkg, quiet=True)
print('NLTK done')
"

echo "=== Build complete! ==="
