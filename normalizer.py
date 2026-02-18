import numpy as np
import joblib
import os
import logging
from typing import Tuple, Optional, Any
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, StandardScaler

# Configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DataPipeline")

class ModelDataPipeline:
    def __init__(self, scaler_type: str = "minmax", artifact_dir: str = "./artifacts"):
        """
        Initialize the pipeline.
        
        Args:
            scaler_type: 'minmax' or 'standard'.
            artifact_dir: Directory to save the fitted scaler for inference later.
        """
        self.artifact_dir = artifact_dir
        self.scaler_path = os.path.join(artifact_dir, "scaler.joblib")
        
        # Select Scaler strategy
        if scaler_type == "minmax":
            self.scaler = MinMaxScaler()
        elif scaler_type == "standard":
            self.scaler = StandardScaler()
        else:
            raise ValueError("Invalid scaler_type. Choose 'minmax' or 'standard'.")
            
        self.is_fitted = False
        os.makedirs(artifact_dir, exist_ok=True)

    def split_data(self, X: np.ndarray, y: np.ndarray, test_size: float = 0.2, random_state: int = 42) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Step 1: Split the Data.
        Crucial: We must split BEFORE we scale to prevent data leakage.
        """
        logger.info(f"Splitting data with test_size={test_size}...")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        logger.info(f"Split complete. Train shape: {X_train.shape}, Test shape: {X_test.shape}")
        return X_train, X_test, y_train, y_test

    def fit_transform_train(self, X_train: np.ndarray) -> np.ndarray:
        """
        Step 2: Fit the Scaler (On Training Data ONLY).
        Step 3a: Transform Training Data.
        """
        logger.info("Fitting scaler on TRAINING data...")
        # Learn the min/max or mean/std from training data only
        X_train_scaled = self.scaler.fit_transform(X_train)
        self.is_fitted = True
        
        # Save the scaler immediately so it can be used for inference later
        self._save_scaler()
        
        return X_train_scaled

    def transform_test(self, X_test: np.ndarray) -> np.ndarray:
        """
        Step 3b: Transform Testing Data.
        Uses the parameters learned from X_train. Do NOT fit here.
        """
        if not self.is_fitted:
            raise RuntimeError("Pipeline is not fitted. Run fit_transform_train first.")
            
        logger.info("Transforming TEST data using training parameters...")
        return self.scaler.transform(X_test)

    def transform_inference(self, X_new: np.ndarray) -> np.ndarray:
        """
        Step 4: Consistency in Prediction.
        Loads the saved scaler to ensure new live data is normalized exactly like the training data.
        """
        if not self.is_fitted:
            self._load_scaler()
            
        return self.scaler.transform(X_new)

    def _save_scaler(self):
        joblib.dump(self.scaler, self.scaler_path)
        logger.info(f"Scaler artifact saved to {self.scaler_path}")

    def _load_scaler(self):
        if not os.path.exists(self.scaler_path):
            raise FileNotFoundError(f"No scaler found at {self.scaler_path}. Train the model first.")
        
        self.scaler = joblib.load(self.scaler_path)
        self.is_fitted = True
        logger.info(f"Scaler loaded from {self.scaler_path}")
