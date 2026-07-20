import os
from PIL import Image
from typing import Optional, List
import torch

class ImageCaptioner:
    def __init__(self, doubao_api_key=None, doubao_model_id=None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.doubao_api_key = doubao_api_key
        self.doubao_model_id = doubao_model_id
        
        print(f"Initializing Image Captioner on {self.device}...")
        
        # 优先使用豆包API
        self.captioner = None
        self.captioner_type = None
        
        if doubao_api_key:
            print("Using Doubao API for image captioning")
            self.captioner_type = "doubao"
        elif os.getenv('SKIP_LOCAL_CAPTION_MODEL', 'False').lower() == 'true':
            print("Skipping local BLIP model; using fallback captioning")
            self.captioner_type = "fallback"
        else:
            # 尝试使用BLIP
            try:
                from transformers import BlipProcessor, BlipForConditionalGeneration
                print("Loading BLIP model for image captioning...")
                self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
                self.captioner = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(self.device)
                self.captioner_type = "blip"
                print("BLIP model loaded successfully")
            except Exception as e:
                print(f"Failed to load BLIP: {e}")
                print("Will use simple fallback captioning")
                self.captioner_type = "fallback"
    
    def generate_caption(self, image_path: str, style: Optional[str] = None) -> str:
        """
        Generate image caption using multimodal analysis
        
        Args:
            image_path: Path to the image
            style: Optional style info to add to the caption
            
        Returns:
            Generated image caption
        """
        try:
            if self.captioner_type == "doubao":
                return self._doubao_caption(image_path, style)
                
            elif self.captioner_type == "blip":
                return self._blip_caption(image_path, style)
            
            else:
                # 简单的回退方案
                return self._fallback_caption(image_path, style)
                
        except Exception as e:
            print(f"Error generating caption: {e}")
            return self._fallback_caption(image_path, style)
    
    def _doubao_caption(self, image_path: str, style: Optional[str] = None) -> str:
        """
        Use Doubao API for image captioning
        """
        try:
            import base64
            import requests
            
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 豆包API调用 - 使用正确的格式
            url = "https://ark.cn-beijing.volces.com/api/v3/responses"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.doubao_api_key}"
            }
            
            prompt = "Please describe this image briefly in English, including main objects, scene, colors, no more than 30 words"
            if style:
                prompt += f", {style} style"
            
            payload = {
                "model": self.doubao_model_id or "doubao-seed-2-0-lite-260428",
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{base64_image}"
                            },
                            {
                                "type": "input_text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            }
            
            print(f"Calling Doubao API with model: {self.doubao_model_id}")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code != 200:
                print(f"Doubao API returned status {response.status_code}: {response.text}")
                print("Falling back to simple captioning...")
                return self._fallback_caption(image_path, style)
            
            result = response.json()
            
            # 从响应中获取生成的描述
            caption = ""
            if "output" in result:
                for output_item in result["output"]:
                    if output_item.get("type") == "message":
                        content_list = output_item.get("content", [])
                        for content_item in content_list:
                            if content_item.get("type") == "output_text":
                                caption = content_item.get("text", "").strip()
                                break
                        if caption:
                            break
            
            if caption:
                print(f"Doubao generated caption: {caption}")
                return caption
            else:
                print("Doubao returned empty caption, falling back...")
                return self._fallback_caption(image_path, style)
            
        except Exception as e:
            print(f"Doubao API error: {e}")
            print("Falling back to simple captioning...")
            return self._fallback_caption(image_path, style)
    
    def extract_keywords_from_caption(self, caption: str, style: str = '') -> list:
        """
        从图片描述中提取关键词
        """
        if not self.doubao_api_key:
            # 如果没有豆包API密钥，使用简单的关键词提取
            return self._simple_keyword_extraction(caption, style)
        
        try:
            import requests
            
            url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.doubao_api_key}"
            }
            
            prompt = f"""请从以下图片描述中提取2-4个最核心的英文关键词，用于图像搜索。
只返回关键词，用逗号分隔，不要有其他内容。

图片描述：{caption}
风格信息：{style if style else '无'}"""
            
            payload = {
                "model": self.doubao_model_id or "doubao-seed-2-0-lite-260428",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "thinking": {
                    "type": "disabled"
                }
            }
            
            print(f"\n=== Extracting keywords from caption ===")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                keywords_text = ""
                if "choices" in result and len(result["choices"]) > 0:
                    keywords_text = result["choices"][0]["message"]["content"].strip()
                
                # 解析关键词
                keywords = []
                if keywords_text:
                    # 按逗号、空格等分隔符拆分
                    import re
                    parts = re.split(r'[,，\s]+', keywords_text)
                    keywords = [p.strip() for p in parts if p.strip()]
                    # 只保留前4个关键词
                    keywords = keywords[:4]
                
                print(f"Extracted keywords: {keywords}")
                return keywords
            else:
                print(f"Keyword extraction API error: {response.status_code}")
                return self._simple_keyword_extraction(caption, style)
                
        except Exception as e:
            print(f"Keyword extraction error: {e}")
            return self._simple_keyword_extraction(caption, style)
    
    def _simple_keyword_extraction(self, caption: str, style: str = '') -> list:
        """
        简单的关键词提取（回退方案）
        """
        keywords = []
        if style:
            keywords.append(style)
        # 从描述中提取单词（简单按空格拆分）
        words = caption.split()
        for word in words[:3]:
            word = word.strip('.,!?')
            if word and word not in keywords:
                keywords.append(word)
        return keywords[:4]
    
    def _blip_caption(self, image_path: str, style: Optional[str] = None) -> str:
        """
        Use BLIP model for image captioning
        """
        try:
            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(image, return_tensors="pt").to(self.device)
            
            out = self.captioner.generate(**inputs, max_length=50, num_beams=3)
            caption = self.processor.decode(out[0], skip_special_tokens=True)
            
            # 结合风格信息
            if style:
                return f"{caption}, {style} style"
            return caption
        except Exception as e:
            print(f"BLIP error: {e}")
            return self._fallback_caption(image_path, style)
    
    def _fallback_caption(self, image_path: str, style: Optional[str] = None) -> str:
        """
        Simple fallback caption when other methods are not available
        """
        filename = os.path.basename(image_path)
        base_name = os.path.splitext(filename)[0]
        
        # 如果有风格信息，就用风格作为主要搜索词
        if style:
            return f"{style} image"
        return f"reference image"
    
    def generate_reference_images(self, image_path: str, caption: str, style: str, num_images: int = 3) -> dict:
        """
        使用豆包生图模型根据结果图和描述生成参考图
        
        Args:
            image_path: 结果图路径
            caption: 图片描述
            style: 目标风格
            num_images: 要生成的图片数量
            
        Returns:
            dict: 包含生成的图片URL列表和prompt
        """
        if not self.doubao_api_key:
            print("No Doubao API key, cannot generate reference images")
            return {'prompt': '', 'images': [], 'error': 'API key not configured'}
        
        try:
            import base64
            import requests
            
            print(f"\n=== Generating {num_images} reference images ===")
            
            # 构建生图prompt
            prompt = self._build_generation_prompt(caption, style)
            print(f"Generation prompt: {prompt}")
            
            # 读取图片并转为base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 调用生图API
            url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.doubao_api_key}"
            }
            
            payload = {
                "model": "doubao-seedream-5-0-260128",
                "prompt": prompt,
                "image": [f"data:image/jpeg;base64,{base64_image}"],
                "sequential_image_generation": "auto",
                "sequential_image_generation_options": {
                    "max_images": num_images
                },
                "response_format": "url",
                "size": "2K",
                "stream": False,
                "watermark": True
            }
            
            print("Calling Doubao image generation API...")
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            
            if response.status_code != 200:
                print(f"Image generation API error: {response.status_code} - {response.text}")
                return {
                    'prompt': prompt,
                    'images': [],
                    'error': f"API error: {response.status_code}"
                }
            
            result = response.json()
            print(f"Image generation response: {result}")
            
            # 解析生成的图片URL - 支持多种响应格式
            images = []
            
            # 格式1: data数组
            if "data" in result and isinstance(result["data"], list):
                for item in result["data"]:
                    if isinstance(item, dict) and "url" in item:
                        images.append(item["url"])
                    elif isinstance(item, str):
                        images.append(item)
            
            # 格式2: images数组
            elif "images" in result and isinstance(result["images"], list):
                for item in result["images"]:
                    if isinstance(item, dict) and "url" in item:
                        images.append(item["url"])
                    elif isinstance(item, str):
                        images.append(item)
            
            # 格式3: 单个url字段
            elif "url" in result:
                images.append(result["url"])
            
            # 格式4: output数组
            elif "output" in result and isinstance(result["output"], list):
                for item in result["output"]:
                    if isinstance(item, dict):
                        if "url" in item:
                            images.append(item["url"])
                        elif "image" in item:
                            images.append(item["image"])
            
            print(f"Generated {len(images)} images")
            
            return {
                'prompt': prompt,
                'images': images,
                'error': None if images else 'No images generated'
            }
            
        except Exception as e:
            print(f"Image generation error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'prompt': '',
                'images': [],
                'error': str(e)
            }
    
    def _build_generation_prompt(self, caption: str, style: str) -> str:
        """
        构建生图prompt，结合描述和风格
        """
        prompt_parts = []
        
        # 添加描述
        if caption:
            prompt_parts.append(caption)
        
        # 添加风格
        if style:
            prompt_parts.append(f"{style} style")
        
        # 组合prompt
        prompt = ", ".join(prompt_parts)
        
        # 确保prompt足够具体
        if len(prompt) < 20:
            prompt = f"Reference image in {style} style, high quality, detailed"
        
        return prompt
    
    def generate_text_to_image(self, style: str, caption: str = "", num_images: int = 3, case_name: str = "") -> dict:
        """
        使用豆包文生图模型根据风格词生成参考图（不使用参考图）
        
        Args:
            style: 目标风格
            caption: 可选的图片描述（用于丰富prompt）
            num_images: 要生成的图片数量
            case_name: 案例名称，用于保存图片到本地
            
        Returns:
            dict: 包含生成的图片本地路径列表和prompt
        """
        if not self.doubao_api_key:
            print("No Doubao API key, cannot generate reference images")
            return {'prompt': '', 'images': [], 'error': 'API key not configured'}
        
        try:
            import requests
            import uuid
            
            print(f"\n=== Generating {num_images} reference images from text ===")
            
            # 构建文生图prompt，主要使用风格词
            prompt = self._build_text_to_image_prompt(style, caption)
            print(f"Text-to-image prompt: {prompt}")
            
            # 调用文生图API
            url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.doubao_api_key}"
            }
            
            payload = {
                "model": "doubao-seedream-5-0-260128",
                "prompt": prompt,
                "size": "2K",
                "output_format": "png",
                "watermark": False
            }
            
            print("Calling Doubao text-to-image API...")
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            
            if response.status_code != 200:
                print(f"Text-to-image API error: {response.status_code} - {response.text}")
                return {
                    'prompt': prompt,
                    'images': [],
                    'error': f"API error: {response.status_code}"
                }
            
            result = response.json()
            print(f"Text-to-image response: {result}")
            
            # 解析生成的图片URL
            image_urls = []
            if "data" in result and isinstance(result["data"], list):
                for item in result["data"]:
                    if isinstance(item, dict) and "url" in item:
                        image_urls.append(item["url"])
                    elif isinstance(item, str):
                        image_urls.append(item)
            
            # 如果返回图片不够，尝试使用其他响应格式
            elif "images" in result and isinstance(result["images"], list):
                for item in result["images"]:
                    if isinstance(item, dict) and "url" in item:
                        image_urls.append(item["url"])
                    elif isinstance(item, str):
                        image_urls.append(item)
            
            # 只取需要的数量
            image_urls = image_urls[:num_images]
            
            # 下载图片到本地
            local_images = []
            if image_urls and case_name:
                # 创建保存目录
                save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                       'generated_images', case_name)
                os.makedirs(save_dir, exist_ok=True)
                
                for idx, img_url in enumerate(image_urls):
                    try:
                        print(f"Downloading image {idx+1}/{len(image_urls)}...")
                        img_response = requests.get(img_url, timeout=30)
                        if img_response.status_code == 200:
                            # 生成唯一文件名
                            filename = f"generated_{idx}_{uuid.uuid4().hex[:8]}.png"
                            filepath = os.path.join(save_dir, filename)
                            
                            # 保存图片
                            with open(filepath, 'wb') as f:
                                f.write(img_response.content)
                            
                            # 保存相对路径
                            rel_path = f"/generated_images/{case_name}/{filename}"
                            local_images.append(rel_path)
                            print(f"Saved to: {filepath}")
                        else:
                            print(f"Failed to download image {idx+1}: {img_response.status_code}")
                    except Exception as e:
                        print(f"Error downloading image {idx+1}: {e}")
            
            print(f"Generated {len(local_images)} images locally")
            
            return {
                'prompt': prompt,
                'images': local_images,
                'error': None if local_images else 'No images generated'
            }
            
        except Exception as e:
            print(f"Text-to-image generation error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'prompt': '',
                'images': [],
                'error': str(e)
            }
    
    def _build_text_to_image_prompt(self, style: str, caption: str = "") -> str:
        """
        构建文生图prompt，主要基于风格词，更加丰富和专业
        """
        # 基础风格描述
        style_prompts = {
            "vintage": "复古风格摄影，胶片质感，温暖色调，怀旧氛围，经典构图，柔光效果",
            "modern": "现代简约风格，几何构图，简洁干净，线条流畅，当代艺术感",
            "minimalist": "极简主义，留白空间，简约色彩，纯粹构图，高级感",
            "cinematic": "电影感画面，戏剧性光影，宽幅构图，叙事感，好莱坞风格",
            "film": "胶片摄影质感，颗粒感，复古色调，真实自然，电影感",
            "digital": "数字艺术风格，未来感，科技感，高对比度，鲜艳色彩",
            "portrait": "人像摄影，专业打光，细腻质感，情绪表达，商业人像",
            "landscape": "风景摄影，大场景，自然光线，壮美构图，风光大片",
            "fashion": "时尚摄影，高级感，潮流风格，专业布光，时装大片",
            "product": "产品摄影，商业质感，清晰细节，专业打光，静物大片"
        }
        
        # 获取风格对应的详细描述，如果没有则使用通用描述
        style_detail = style_prompts.get(style.lower(), f"高品质{style}风格图片，专业摄影水准")
        
        prompt_parts = []
        
        # 添加核心风格描述
        prompt_parts.append(style_detail)
        
        # 添加通用高品质要求
        prompt_parts.extend([
            "高品质，8K分辨率，细节丰富，清晰锐利",
            "专业摄影，专业打光，色彩准确，构图完美",
            "艺术感强，视觉冲击力，具有参考价值的设计参考图",
            "无水印，无文字，适合作为设计参考"
        ])
        
        # 组合prompt
        prompt = "，".join(prompt_parts)
        
        return prompt

