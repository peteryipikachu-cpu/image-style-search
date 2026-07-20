import os
import pandas as pd
from tqdm import tqdm
from config import Config
from .database import Database
from .feature_extractor import FeatureExtractor
from .image_caption import ImageCaptioner

class Preprocessor:
    def __init__(self, db_config=None):
        self.db = Database(db_config)
        self.extractor = FeatureExtractor()
        self.captioner = ImageCaptioner()
    
    def init_database(self):
        print("Initializing database...")
        self.db.init_database()
        print("Database initialized!")
    
    def process_parquet(self, parquet_path, image_base_path="", batch_size=100, limit=None):
        print(f"Loading parquet file: {parquet_path}")
        df = pd.read_parquet(parquet_path)
        
        if limit:
            df = df.head(limit)
        
        print(f"Total images to process: {len(df)}")
        
        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing images"):
            image_id = row['image_id']
            file_path = row['file_path']
            
            if image_base_path:
                full_path = os.path.join(image_base_path, file_path)
            else:
                full_path = file_path
            
            if not os.path.exists(full_path):
                print(f"Warning: File not found - {full_path}")
                continue
            
            try:
                category = row.get('category', '')
                keywords = row.get('keywords', '')
                
                image_vector = self.extractor.extract_image_features(full_path)
                
                image_desc = self.captioner.generate_caption(full_path)
                
                combined_text = f"{category}. {keywords}. {image_desc}"
                text_vector = self.extractor.extract_text_features(combined_text)
                
                self.db.insert_image_feature(
                    image_id=image_id,
                    file_path=file_path,
                    file_name=row.get('file_name', ''),
                    category=category,
                    image_desc=image_desc,
                    keywords=keywords,
                    image_vector=image_vector,
                    text_vector=text_vector
                )
                
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
        
        print(f"Process complete! Total in database: {self.db.get_count()}")
    
    def process_directory(self, directory_path, batch_size=100):
        print(f"Scanning directory: {directory_path}")
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        image_paths = []
        
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if os.path.splitext(file)[1].lower() in image_extensions:
                    image_paths.append(os.path.join(root, file))
        
        print(f"Found {len(image_paths)} images")
        
        for idx, image_path in enumerate(tqdm(image_paths, desc="Processing images")):
            try:
                image_id = os.path.splitext(os.path.basename(image_path))[0]
                category = os.path.basename(os.path.dirname(image_path))
                
                image_vector = self.extractor.extract_image_features(image_path)
                
                image_desc = self.captioner.generate_caption(image_path)
                
                combined_text = f"{category}. {image_desc}"
                text_vector = self.extractor.extract_text_features(combined_text)
                
                self.db.insert_image_feature(
                    image_id=image_id,
                    file_path=image_path,
                    file_name=os.path.basename(image_path),
                    category=category,
                    image_desc=image_desc,
                    keywords='',
                    image_vector=image_vector,
                    text_vector=text_vector
                )
                
            except Exception as e:
                print(f"Error processing {image_path}: {e}")
        
        print(f"Process complete! Total in database: {self.db.get_count()}")
    
    def get_status(self):
        return {
            'count': self.db.get_count()
        }
