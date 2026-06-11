"""
Anomaly detection algorithms.
"""
from typing import List, Tuple, Optional
import numpy as np
from config import get_logger

logger = get_logger(__name__)


class AnomalyDetector:
    """Detect anomalies in data."""

    @staticmethod
    def detect_zscore(
        values: List[float], threshold: float = 3.0
    ) -> List[Tuple[int, float]]:
        """Detect anomalies using Z-score method.
        
        Returns list of (index, zscore) tuples for anomalies.
        """
        try:
            arr = np.array(values)
            mean = np.mean(arr)
            std = np.std(arr)

            if std == 0:
                return []

            zscores = np.abs((arr - mean) / std)
            anomalies = [
                (int(i), float(zscores[i]))
                for i, z in enumerate(zscores)
                if z > threshold
            ]

            logger.debug(f"Found {len(anomalies)} anomalies using Z-score")
            return anomalies

        except Exception as e:
            logger.error(f"Z-score anomaly detection failed: {e}")
            return []

    @staticmethod
    def detect_iqr(values: List[float]) -> List[Tuple[int, float]]:
        """Detect anomalies using Interquartile Range (IQR) method.
        
        Returns list of (index, value) tuples for anomalies.
        """
        try:
            arr = np.array(values)
            q1 = np.percentile(arr, 25)
            q3 = np.percentile(arr, 75)
            iqr = q3 - q1

            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            anomalies = [
                (int(i), float(v))
                for i, v in enumerate(arr)
                if v < lower_bound or v > upper_bound
            ]

            logger.debug(f"Found {len(anomalies)} anomalies using IQR")
            return anomalies

        except Exception as e:
            logger.error(f"IQR anomaly detection failed: {e}")
            return []

    @staticmethod
    def detect_isolation_forest(
        values: List[float], contamination: float = 0.1
    ) -> List[Tuple[int, bool]]:
        """Detect anomalies using Isolation Forest.
        
        Returns list of (index, is_anomaly) tuples.
        """
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            logger.warning(
                "scikit-learn not installed. Falling back to Z-score method."
            )
            return AnomalyDetector.detect_zscore(values)

        try:
            arr = np.array(values).reshape(-1, 1)
            clf = IsolationForest(contamination=contamination, random_state=42)
            predictions = clf.fit_predict(arr)

            anomalies = [
                (int(i), pred == -1)
                for i, pred in enumerate(predictions)
                if pred == -1
            ]

            logger.debug(f"Found {len(anomalies)} anomalies using Isolation Forest")
            return anomalies

        except Exception as e:
            logger.error(f"Isolation Forest anomaly detection failed: {e}")
            return []
