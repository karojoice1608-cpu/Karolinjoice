import os
import cv2
import numpy as np
import argparse
import joblib
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_features(image_path: str) -> Optional[list]:
    """
    Extracts features from an image file.
    These features are:
    1. Laplacian variance
    2. Number of unique color shades
    3. Max single color dominance percentage
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            logging.warning(f"Could not read image: {image_path}")
            return None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        total_pixels = gray.shape[0] * gray.shape[1]

        # Metric 1: Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = laplacian.var()

        # Metric 2: Color diversity
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
        significant_threshold = total_pixels * 0.001
        unique_colors = int(np.sum(hist > significant_threshold))

        # Metric 3: Max single color dominance
        max_color_pct = (np.max(hist) / total_pixels) * 100

        return [laplacian_var, unique_colors, max_color_pct]

    except Exception as e:
        logging.error(f"Failed to process {image_path}: {e}")
        return None

def train_model(dataset_path: str):
    """
    Trains a logistic regression model to classify images as 'born_digital' or 'scene_text'.

    The dataset directory should contain two subdirectories:
    - 'born_digital': containing born-digital images (e.g., screenshots)
    - 'scene_text': containing scene text images (e.g., photos)
    """
    features = []
    labels = []

    born_digital_path = os.path.join(dataset_path, 'born_digital')
    scene_text_path = os.path.join(dataset_path, 'scene_text')

    if not os.path.isdir(born_digital_path) or not os.path.isdir(scene_text_path):
        logging.error("Dataset directory must contain 'born_digital' and 'scene_text' subdirectories.")
        return

    # Process born_digital images
    logging.info(f"Processing born_digital images from: {born_digital_path}")
    for filename in os.listdir(born_digital_path):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            image_path = os.path.join(born_digital_path, filename)
            feature_vector = extract_features(image_path)
            if feature_vector:
                features.append(feature_vector)
                labels.append(0) # 0 for born_digital

    # Process scene_text images
    logging.info(f"Processing scene_text images from: {scene_text_path}")
    for filename in os.listdir(scene_text_path):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            image_path = os.path.join(scene_text_path, filename)
            feature_vector = extract_features(image_path)
            if feature_vector:
                features.append(feature_vector)
                labels.append(1) # 1 for scene_text

    if not features:
        logging.error("No features extracted. Check your dataset.")
        return

    X = np.array(features)
    y = np.array(labels)

    # Split data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Train a logistic regression model
    logging.info("Training the logistic regression model...")
    model = LogisticRegression(random_state=42, class_weight='balanced')
    model.fit(X_train, y_train)

    # Evaluate the model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    logging.info(f"Model accuracy: {accuracy:.2f}")
    logging.info("Classification Report:")
    logging.info(classification_report(y_test, y_pred, target_names=['born_digital', 'scene_text']))

    # Save the trained model
    model_path = 'image_classifier.joblib'
    joblib.dump(model, model_path)
    logging.info(f"Model saved to {model_path}")
    logging.info("
Training complete. You can now use the generated 'image_classifier.joblib' in your application.")
    logging.info("You will need to modify 'app/services/image_service.py' to use this model.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Train an image classifier.")
    parser.add_argument("dataset_path", type=str, help="Path to the dataset directory.")
    args = parser.parse_args()

    train_model(args.dataset_path)
