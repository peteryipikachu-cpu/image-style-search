import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import os

class ImageCaptioner:
    def __init__(self, model_name="Salesforce/blip-image-captioning-base"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading BLIP model on {self.device}...")
        self.processor = BlipProcessor.from_pretrained(model_name)
        self.model = BlipForConditionalGeneration.from_pretrained(model_name).to(self.device)
        self.model.eval()
    
    def generate_caption(self, image_path):
        try:
            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(image, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                out = self.model.generate(**inputs, max_new_tokens=50)
            
            caption = self.processor.decode(out[0], skip_special_tokens=True)
            return caption
        except Exception as e:
            print(f"Error generating caption for {image_path}: {e}")
            return ""
