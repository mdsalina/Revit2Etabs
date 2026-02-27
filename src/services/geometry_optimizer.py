import numpy as np
from sklearn.cluster import DBSCAN
from collections import Counter
import logging

logger = logging.getLogger("Revit2Etabs")

class GeometryOptimizer:
    def __init__(self, model):
        self.model = model


