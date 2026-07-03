# Use a lightweight official Python image
FROM python:3.11-slim

# Install system dependencies for OpenCV and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set up user with UID 1000 (required for Hugging Face Spaces)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

WORKDIR $HOME/app

# Copy requirements and install dependencies
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Pre-download NLTK resources to cache inside Docker image (improves start time)
RUN python -c " \
import nltk; \
nltk.download('punkt', quiet=True); \
nltk.download('punkt_tab', quiet=True); \
nltk.download('stopwords', quiet=True); \
nltk.download('wordnet', quiet=True); \
nltk.download('averaged_perceptron_tagger', quiet=True) \
"

# Pre-download the CRAFT detection model for EasyOCR
RUN python -c " \
import easyocr; \
easyocr.Reader(['en'], gpu=False) \
"

# Pre-download the sentence-transformers model
RUN python -c " \
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2') \
"

# Copy the rest of the application files
COPY --chown=user . .

# Expose port 7860 (Hugging Face standard)
EXPOSE 7860

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
