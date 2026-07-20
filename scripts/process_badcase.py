#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.preprocessor import Preprocessor
from src.database import Database

def main():
    print("=" * 60)
    print("Image Search - Badcase Processing Tool")
    print("=" * 60)
    
    db_config = {
        'dbname': os.getenv('DB_NAME', 'image_search'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', ''),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432')
    }
    
    preprocessor = Preprocessor(db_config)
    
    print("\n1. Initializing database...")
    preprocessor.init_database()
    
    print("\n2. Processing badcase images...")
    data_dir = os.getenv('DATA_DIR', '/Users/pikachu/work/bodeng/yitusoutu/以图搜图_badcase')
    preprocessor.process_directory(data_dir)
    
    print("\nProcessing complete!")
    status = preprocessor.get_status()
    print(f"Total images in database: {status['count']}")

if __name__ == "__main__":
    main()
