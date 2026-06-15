# ml/trainer.py
import pandas as pd
import lightgbm as lgb
import pickle
import os
import logging

logger = logging.getLogger(__name__)

def train_model(dataset_path: str, model_path: str, version_path: str):
    df = pd.read_csv(dataset_path)
    X = df.drop('label', axis=1)
    y = df['label']
    
    # Train-test split
    split = int(len(df) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    clf = lgb.LGBMClassifier(
        n_estimators=100,
        learning_rate=0.05,
        num_leaves=31,
        objective='multiclass',
        random_state=42,
        verbosity=-1
    )
    
    logger.info("Training LightGBM model...")
    clf.fit(X_train, y_train)
    
    accuracy = clf.score(X_test, y_test)
    logger.info(f"Model trained. Validation Accuracy: {accuracy:.4f}")
    
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, 'wb') as f:
        pickle.dump(clf, f)
    
    with open(version_path, 'w') as f:
        f.write(f"v1.0.0 - Accuracy: {accuracy:.4f}")
    
    logger.info(f"Model saved to {model_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train_model('data/training_data.csv', 'models/footy_model_v1.pkl', 'models/model_version.txt')
