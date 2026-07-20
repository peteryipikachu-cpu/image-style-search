import clip
import torch
import numpy as np
from PIL import Image
from typing import List, Union

class FeatureExtractor:
    def __init__(self, model_name: str = "ViT-B/32"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading CLIP model {model_name} on {self.device}...")
        self.model, self.preprocess = clip.load(model_name, device=self.device)
        self.model.eval()
    
    def extract_image_features(self, image_path: str) -> np.ndarray:
        try:
            image = Image.open(image_path).convert("RGB")
            return self._extract_features_from_pil(image)
        except Exception as e:
            print(f"Error extracting features from {image_path}: {e}")
            return None
    
    def extract_image_features_from_pil(self, image: Image.Image) -> np.ndarray:
        """
        从PIL图像对象提取特征
        
        Args:
            image: PIL图像对象
            
        Returns:
            特征向量
        """
        try:
            return self._extract_features_from_pil(image)
        except Exception as e:
            print(f"Error extracting features from PIL image: {e}")
            return None
    
    def _extract_features_from_pil(self, image: Image.Image) -> np.ndarray:
        """
        内部方法：从PIL图像提取特征
        """
        image = image.convert("RGB")
        image_input = self.preprocess(image).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            features = self.model.encode_image(image_input)
        
        features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().numpy().flatten()
    
    def extract_text_features(self, text: str) -> np.ndarray:
        try:
            text_input = clip.tokenize([text], truncate=True).to(self.device)
            
            with torch.no_grad():
                features = self.model.encode_text(text_input)
            
            features = features / features.norm(dim=-1, keepdim=True)
            return features.cpu().numpy().flatten()
        except Exception as e:
            print(f"Error extracting text features: {e}")
            return None
    
    def extract_batch_features(self, image_paths: List[str]) -> np.ndarray:
        features_list = []
        
        for path in image_paths:
            feat = self.extract_image_features(path)
            if feat is not None:
                features_list.append(feat)
        
        if not features_list:
            return np.array([])
        
        return np.vstack(features_list)